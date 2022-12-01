from dataclasses import dataclass

from touch_sdk.ble_connector import BLEConnector
# pylint: disable=no-name-in-module
from touch_sdk.protobuf.watch_output_pb2 import Update, Gesture, TouchEvent


__doc__ = """Discovering Touch SDK compatible BLE devices and interfacing with them."""


# GATT related UUIDs
# INTERACTION_SERVICE is needed for scanning while the Wear OS
# app is backwards compatible. Only one service UUID can be
# advertised.
INTERACTION_SERVICE = "008e74d0-7bb3-4ac5-8baf-e5e372cced76"
PROTOBUF_SERVICE = "f9d60370-5325-4c64-b874-a68c7c555bad"
PROTOBUF_OUTPUT = "f9d60371-5325-4c64-b874-a68c7c555bad"


@dataclass(frozen=True)
class SensorFrame:
    """A Frozen container class for values of all streamable Touch SDK sensors."""
    acceleration: tuple[float]
    gravity: tuple[float]
    angular_velocity: tuple[float]
    orientation: tuple[float]


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
            self._handle_connect,
            INTERACTION_SERVICE,
            name_filter
        )
        self.connected = False

    def start(self):
        """Blocking event loop that starts the Bluetooth scanner.

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
        client = self._connector.devices[device]
        def wrap_protobuf(callback):
            async def wrapped(_, data):
                message = Update()
                message.ParseFromString(bytes(data))

                if all(s != Update.Signal.DISCONNECT for s in message.signals):
                    if not self.connected:
                        self.connected = True
                        await self._connector.disconnect_devices(exclude=device)
                        print(f'Connected to {name}')
                    await callback(message)
                else:
                    await client.disconnect()

            return wrapped

        try:
            await client.start_notify(PROTOBUF_OUTPUT, wrap_protobuf(self._on_protobuf))
        except ValueError:
            # Sometimes there is a race condition in BLEConnector and _handle_connect
            # gets called twice for the same device. Calling client.start_notify twice
            # will result in an error.
            pass

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
        self._proto_on_sensors(message.sensorFrames)
        self._proto_on_gestures(message.gestures)
        self._proto_on_button_events(message.buttonEvents)
        self._proto_on_touch_events(message.touchEvents)
        self._proto_on_rotary_events(message.rotaryEvents)

    def _proto_on_sensors(self, frames):
        frame = frames[-1]
        self.on_sensors(
            SensorFrame(
                acceleration=self._protovec3_to_tuple(frame.acc),
                gravity=self._protovec3_to_tuple(frame.grav),
                angular_velocity=self._protovec3_to_tuple(frame.gyro),
                orientation=self._protoquat_to_tuple(frame.quat),
            )
        )

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

    def on_sensors(self, sensor_frame):
        """Callback when accelerometer, gyroscope, gravity and orientation
        is changes. Guaranteed to have all the four sensors in every update."""

    def on_tap(self):
        """Called when the tap gesture happens."""

    def on_touch_down(self, x, y):
        """Touch screen touch starts."""

    def on_touch_up(self, x, y):
        """Touch screen touch ends."""

    def on_touch_move(self, x, y):
        """Touch screen touch moves."""

    def on_touch_cancel(self, x, y):
        """Touch screen touch becomes a swipe gesture that goes to another view."""

    def on_rotary(self, direction):
        """Rotary dial around the watch screen is turned.

        direction is +1 for clockwise, -1 for counterclockwise."""

    def on_back_button(self):
        """Back button of the watch is pressed and released.

        Wear OS does not support separate button down and button up events."""
