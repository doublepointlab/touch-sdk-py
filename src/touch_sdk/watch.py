from dataclasses import dataclass
from enum import Enum
import asyncio
from typing import Tuple, Optional
import sys
import platform
import struct
import re
from itertools import accumulate, chain

from touch_sdk.utils import pairwise
from touch_sdk.ble_connector import BLEConnector

# pylint: disable=no-name-in-module
from touch_sdk.protobuf.watch_output_pb2 import Update, Gesture, TouchEvent
from touch_sdk.protobuf.watch_input_pb2 import InputUpdate, HapticEvent, ClientInfo


__doc__ = """Discovering Touch SDK compatible BLE devices and interfacing with them."""


# GATT related UUIDs
# INTERACTION_SERVICE is needed for scanning while the Wear OS
# app is backwards compatible. Only one service UUID can be
# advertised.
INTERACTION_SERVICE = "008e74d0-7bb3-4ac5-8baf-e5e372cced76"
PROTOBUF_SERVICE = "f9d60370-5325-4c64-b874-a68c7c555bad"
PROTOBUF_OUTPUT = "f9d60371-5325-4c64-b874-a68c7c555bad"
PROTOBUF_INPUT = "f9d60372-5325-4c64-b874-a68c7c555bad"


@dataclass(frozen=True)
class SensorFrame:
    """A Frozen container class for values of all streamable Touch SDK sensors."""

    acceleration: Tuple[float]
    gravity: Tuple[float]
    angular_velocity: Tuple[float]
    orientation: Tuple[float]
    magnetic_field: Optional[Tuple[float]]
    magnetic_field_calibration: Optional[Tuple[float]]
    timestamp: int


class Hand(Enum):
    """Which hand the watch is worn on."""

    NONE = 0
    RIGHT = 1
    LEFT = 2


class Watch:
    """Scans Touch SDK compatible Bluetooth LE devices and connects to all of them.

    After the controller device accepts a connection, Watch disconnects other devices.

    Watch also parses the data that comes over Bluetooth and returns it through
    callback methods."""

    def __init__(self, name_filter=None):
        """Creates a new instance of Watch. Does not start scanning for Bluetooth
        devices. Use Watch.start to enter the scanning and connection event loop.

        Optional name_filter connects only to watches with that name (case insensitive)"""
        self._connector = BLEConnector(
            self._handle_connect, INTERACTION_SERVICE, name_filter
        )

        self.custom_data = None
        if hasattr(self.__class__, 'custom_data'):
            self.custom_data = self.__class__.custom_data

        self.client = None
        self.hand = Hand.NONE

    def start(self):
        """Blocking event loop that starts the Bluetooth scanner

        More handy than Watch.run when only this event loop is needed."""
        self._connector.start()

    async def run(self):
        """Asynchronous blocking event loop that starts the Bluetooth scanner.

        Makes it possible to run multiple async event loops with e.g. asyncio.gather."""
        await self._connector.run()

    def stop(self):
        """Stops bluetooth scanner and disconnects Bluetooth devices."""
        self._connector.stop()

    async def _handle_connect(self, device, name):
        # In the situation when there are multiple Touch SDK compatible watches available,
        # `_handle_connect` will be called for each. `client` will hold the value for one
        # connection, matching `device` and `name`.
        #
        # `self.client` will only be assigned once the watch accepts the connection. This
        # will also call `self._connector.disconnect_devices(exclude=device)`, so the
        # remaining watches should not be able to accept the connection anymore - but if
        # they do, the end result is likely just all watches disconnecting. Not ideal,
        # but no errors.
        #
        # Once the connected watch sends a disconnect signal (`Update.Signal.DISCONNECT`),
        # `self.client` will be deassigned (set to None), and the cycle can start again.

        client = self._connector.devices[device]

        def wrap_protobuf(callback):
            async def wrapped(_, data):
                message = Update()
                message.ParseFromString(bytes(data))

                # Watch sent a disconnect signal. Might be because the user pressed "no"
                # from the connection dialog on the watch (was not connected to begin with),
                # or because the watch app is exiting / user pressed "forget devices" (was
                # connected, a.k.a. self.client == client)
                if any(s == Update.Signal.DISCONNECT for s in message.signals):
                    await self._on_disconnect_signal(client, name)

                # Watch sent some other data, but no disconnect signal = watch accepted
                # the connection
                else:
                    await self._on_data(client, name, device, callback, message)

            return wrapped

        try:
            await client.start_notify(PROTOBUF_OUTPUT, wrap_protobuf(self._on_protobuf))
            await self._subscribe_to_custom_characteristics(client)
            await self._send_client_info(client)

        except ValueError:
            # Sometimes there is a race condition in BLEConnector and _handle_connect
            # gets called twice for the same device. Calling client.start_notify twice
            # will result in an error.
            pass

    async def _subscribe_to_custom_characteristics(self, client):
        if self.custom_data is None:
            return

        subscriptions = [
            client.start_notify(uuid, self._on_custom_data) for uuid in self.custom_data
        ]
        await asyncio.gather(*subscriptions)

    async def _on_custom_data(self, characteristic, data):
        fmt = self.custom_data.get(characteristic.uuid)

        if fmt is None:
            return

        endianness_tokens = "@<>=!"

        format_description = fmt if fmt[0] in endianness_tokens else '@' + fmt

        format_strings = re.split(f"(?=[{endianness_tokens}])", format_description)

        sizes = [struct.calcsize(fmt) for fmt in format_strings]
        ranges = pairwise(accumulate(sizes))
        data_pieces = [data[start:end] for start, end in ranges]

        nestedContent = [
            struct.unpack(fmt, piece)
            for piece, fmt in zip(data_pieces, format_strings[1:])
        ]
        content = tuple(chain(*nestedContent))

        self.on_custom_data(characteristic.uuid, content)

    async def _send_client_info(self, client):
        client_info = ClientInfo()
        client_info.appName = sys.argv[0]
        client_info.deviceName = platform.node()
        client_info.os = platform.system()
        input_update = InputUpdate()
        input_update.clientInfo.CopyFrom(client_info)
        await client.write_gatt_char(PROTOBUF_INPUT, input_update.SerializeToString())

    async def _on_disconnect_signal(self, client, name):
        # As a GATT server, the watch can't actually disconnect on its own.
        # However, they want this connection to be ended, so the client side disconnects.
        await client.disconnect()

        # This client had accepted the connection before -> "disconnected"
        if self.client == client:
            print(f"Disconnected from {name}")
            self.client = None
            await self._connector.start_scanner()

        # This client had NOT accepted the connection before -> "declined"
        else:
            print(f"Connection declined from {name}")

    async def _on_data(self, client, name, device, callback, message):
        if not self.client:
            print(f"Connected to {name}")
            self.client = client
            await self._connector.disconnect_devices(exclude=device)
            await self._fetch_info()

        # Parse and handle the actual data
        if self.client == client:
            await callback(message)

        # Connection accepted from a second (this) device at the same time -> cancel
        # connection. Generally this code path should not happen, but with an unlucky
        # timing it's possible.
        else:
            await client.disconnect()

    async def _fetch_info(self):
        data = await self.client.read_gatt_char(PROTOBUF_OUTPUT)
        update = Update()
        update.ParseFromString(bytes(data))
        if update.HasField("info"):
            self.hand = Hand(update.info.hand)

    @staticmethod
    def _protovec2_to_tuple(vec):
        return (vec.x, vec.y)

    @staticmethod
    def _protovec3_to_tuple(vec):
        return (vec.x, vec.y, vec.z)

    @staticmethod
    def _protoquat_to_tuple(vec):
        return (vec.x, vec.y, vec.z, vec.w)

    async def _on_protobuf(self, message):
        self._proto_on_sensors(message.sensorFrames, message.unixTime)
        self._proto_on_gestures(message.gestures)
        self._proto_on_button_events(message.buttonEvents)
        self._proto_on_touch_events(message.touchEvents)
        self._proto_on_rotary_events(message.rotaryEvents)

        if message.HasField("info"):
            self._proto_on_info(message.info)

    def _proto_on_sensors(self, frames, timestamp):
        frame = frames[-1]
        sensor_frame = SensorFrame(
            acceleration=self._protovec3_to_tuple(frame.acc),
            gravity=self._protovec3_to_tuple(frame.grav),
            angular_velocity=self._protovec3_to_tuple(frame.gyro),
            orientation=self._protoquat_to_tuple(frame.quat),
            magnetic_field=(
                self._protovec3_to_tuple(frame.mag)
                if frame.HasField("mag")
                else None
            ),
            magnetic_field_calibration=(
                self._protovec3_to_tuple(frame.magCal)
                if frame.HasField("magCal")
                else None
            ),
            timestamp=timestamp
        )
        self.on_sensors(sensor_frame)
        self._on_arm_direction_change(sensor_frame)

    def _proto_on_gestures(self, gestures):
        if any(g.type == Gesture.GestureType.TAP for g in gestures):
            self.on_tap()

    def _proto_on_button_events(self, buttons):
        if any(b.id == 0 for b in buttons):
            self.on_back_button()

    def _proto_on_touch_events(self, touch_events):
        for touch in touch_events:
            coords = self._protovec2_to_tuple(touch.coords[0])
            if touch.eventType == TouchEvent.TouchEventType.BEGIN:
                self.on_touch_down(*coords)
            elif touch.eventType == TouchEvent.TouchEventType.END:
                self.on_touch_up(*coords)
            elif touch.eventType == TouchEvent.TouchEventType.MOVE:
                self.on_touch_move(*coords)
            elif touch.eventType == TouchEvent.TouchEventType.CANCEL:
                self.on_touch_cancel(*coords)

    def _proto_on_rotary_events(self, rotary_events):
        for rotary in rotary_events:
            self.on_rotary(-rotary.step)

    def _proto_on_info(self, info):
        self.hand = Hand(info.hand)

    def _write_input_characteristic(self, data):
        loop = asyncio.get_running_loop()
        loop.create_task(self._async_write_input_characteristic(PROTOBUF_INPUT, data))

    async def _async_write_input_characteristic(self, characteristic, data):
        if self.client:
            await self.client.write_gatt_char(characteristic, data)

    @staticmethod
    def _create_haptics_update(intensity, length):
        clamped_intensity = min(max(intensity, 0.0), 1.0)
        clamped_length = min(max(int(length), 0), 5000)
        haptic_event = HapticEvent()
        haptic_event.type = HapticEvent.HapticType.ONESHOT
        haptic_event.length = clamped_length
        haptic_event.intensity = clamped_intensity
        input_update = InputUpdate()
        input_update.hapticEvent.CopyFrom(haptic_event)
        return input_update

    def _on_arm_direction_change(self, sensor_frame: SensorFrame):
        def normalize(vector):
            length = sum(x * x for x in vector) ** 0.5
            return [x / length for x in vector]

        grav = normalize(sensor_frame.gravity)

        av_x = -sensor_frame.angular_velocity[2]  # right = +
        av_y = -sensor_frame.angular_velocity[1]  # down = +

        handedness_scale = -1 if self.hand == Hand.LEFT else 1

        delta_x = av_x * grav[2] + av_y * grav[1]
        delta_y = handedness_scale * (av_y * grav[2] - av_x * grav[1])

        self.on_arm_direction_change(delta_x, delta_y)

    def on_custom_data(self, uuid: str, content: Tuple):
        """Receive data from custom characteristics"""

    def trigger_haptics(self, intensity: float, duration_ms: int):
        """Trigger vibration haptics on the watch.

        intensity: between 0 and 1
        duration_ms: between 0 and 5000"""
        input_update = self._create_haptics_update(intensity, duration_ms)
        self._write_input_characteristic(input_update.SerializeToString())

    def on_sensors(self, sensor_frame: SensorFrame):
        """Callback when accelerometer, gyroscope, gravity, orientation, and
        magnetic field are changed. Guaranteed to have values for everything but
        magnetic field information in every update."""

    def on_arm_direction_change(self, delta_x: float, delta_y: float):
        """Gyroscope-based raycasting output. Called after sensor updates."""

    def on_tap(self):
        """Called when the tap gesture happens."""

    def on_touch_down(self, x: float, y: float):
        """Touch screen touch starts."""

    def on_touch_up(self, x: float, y: float):
        """Touch screen touch ends."""

    def on_touch_move(self, x: float, y: float):
        """Touch screen touch moves."""

    def on_touch_cancel(self, x: float, y: float):
        """Touch screen touch becomes a swipe gesture that goes to another view."""

    def on_rotary(self, direction: int):
        """Rotary dial around the watch screen is turned.

        direction: +1 for clockwise, -1 for counterclockwise."""

    def on_back_button(self):
        """Back button of the watch is pressed and released.

        Wear OS does not support separate button down and button up events."""
