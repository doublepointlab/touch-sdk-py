from dataclasses import dataclass
from enum import Enum
import asyncio
from typing import Tuple, Optional

from touch_sdk.uuids import PROTOBUF_OUTPUT, PROTOBUF_INPUT
from touch_sdk.utils import unpack_chained
from touch_sdk.watch_connector import WatchConnector

# pylint: disable=no-name-in-module
from touch_sdk.protobuf.watch_output_pb2 import Update, Gesture, TouchEvent
from touch_sdk.protobuf.watch_input_pb2 import InputUpdate, HapticEvent


__doc__ = """Discovering Touch SDK compatible BLE devices and interfacing with them."""


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
    """Scans Touch SDK compatible Bluetooth LE devices and connects to the first one
    of them that approves the connection.

    Watch also parses the data that comes over Bluetooth and returns it through
    callback methods."""

    def __init__(self, name_filter=None):
        """Creates a new instance of Watch. Does not start scanning for Bluetooth
        devices. Use Watch.start to enter the scanning and connection event loop.

        Optional name_filter connects only to watches with that name (case insensitive)"""
        self._connector = WatchConnector(
            self._on_approved_connection, self._on_protobuf, name_filter
        )

        self.custom_data = None
        if hasattr(self.__class__, "custom_data"):
            self.custom_data = self.__class__.custom_data

        self.client = None
        self.hand = Hand.NONE

    def start(self):
        """Blocking event loop that starts the Bluetooth scanner

        More handy than Watch.run when only this event loop is needed."""
        try:
            asyncio.run(self.run())
        except KeyboardInterrupt:
            pass

    async def run(self):
        """Asynchronous blocking event loop that starts the Bluetooth scanner.

        Makes it possible to run multiple async event loops with e.g. asyncio.gather."""
        await self._connector.run()

    async def _on_approved_connection(self, client):
        self.client = client

        await self._fetch_info(client)
        await self._subscribe_to_custom_characteristics(client)

    async def _subscribe_to_custom_characteristics(self, client):
        if self.custom_data is None:
            return

        subscriptions = [
            client.start_notify(uuid, self._on_custom_data) for uuid in self.custom_data
        ]
        await asyncio.gather(*subscriptions)

    async def _on_custom_data(self, characteristic, data):
        format_string = self.custom_data.get(characteristic.uuid)

        if format_string is None:
            return

        content = unpack_chained(format_string, data)

        self.on_custom_data(characteristic.uuid, content)

    async def _fetch_info(self, client):
        data = await client.read_gatt_char(PROTOBUF_OUTPUT)
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
                self._protovec3_to_tuple(frame.mag) if frame.HasField("mag") else None
            ),
            magnetic_field_calibration=(
                self._protovec3_to_tuple(frame.magCal)
                if frame.HasField("magCal")
                else None
            ),
            timestamp=timestamp,
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

    def _write_input_characteristic(self, data, client):
        loop = asyncio.get_running_loop()
        loop.create_task(
            self._async_write_input_characteristic(PROTOBUF_INPUT, data, client)
        )

    async def _async_write_input_characteristic(self, characteristic, data, client):
        if client:
            await client.write_gatt_char(characteristic, data)

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
        self._write_input_characteristic(input_update.SerializeToString(), self.client)

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
