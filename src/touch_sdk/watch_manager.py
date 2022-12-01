import asyncio
from dataclasses import dataclass

from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError
import asyncio_atexit

# pylint: disable=no-name-in-module
from touch_sdk.protobuf.watch_output_pb2 import Update, Gesture, TouchEvent


# GATT related UUIDs
# INTERACTION_SERVICE is needed for scanning while the Wear OS
# app is backwards compatible. Only one service UUID can be
# advertised.
INTERACTION_SERVICE = "008e74d0-7bb3-4ac5-8baf-e5e372cced76"
PROTOBUF_SERVICE = "f9d60370-5325-4c64-b874-a68c7c555bad"
PROTOBUF_OUTPUT = "f9d60371-5325-4c64-b874-a68c7c555bad"

TOUCH_TYPES = {0: "Down", 1: "Up", 2: "Move"}
MOTION_TYPES = {0: "Rotary", 1: "Back button"}
ROTARY_INFOS = {0: "clockwise", 1: "counterclockwise"}
GESTURES = {0: "None", 1: "Tap"}


@dataclass(frozen=True)
class SensorFrame:
    acceleration: tuple[float]
    gravity: tuple[float]
    angular_velocity: tuple[float]
    orientation: tuple[float]


class WatchManager:
    def __init__(self):
        self.found_devices = []
        self.last_device = None
        self.scanner = None
        self.client = None

    def start(self):
        try:
            asyncio.run(self.run())
        except KeyboardInterrupt:
            pass

    async def run(self):
        asyncio_atexit.register(self.stop)
        self.scanner = BleakScanner(
            self._detection_callback, service_uuids=[INTERACTION_SERVICE]
        )
        await self.scanner.start()
        print('Scanning...')
        while True:
            await asyncio.sleep(1)

    async def stop(self):
        await self._disconnect_non_last()
        if self.client:
            await self.client.disconnect()

    async def _detection_callback(self, device, advertisement_data):
        name = (
            advertisement_data.manufacturer_data.get(0xFFFF, bytearray()).decode(
                "utf-8"
            )
            or advertisement_data.local_name
        )

        if INTERACTION_SERVICE in advertisement_data.service_uuids:
            if device in self.found_devices:
                return

            self.found_devices.append(device)

            client = BleakClient(device)
            if client.is_connected:
                return

            print(f"Found {name}")
            self.client = client
            try:
                await self._do_connect(device)
            except asyncio.exceptions.CancelledError:
                print("connection cancelled from", name)
            except BleakError:
                pass

    async def _do_connect(self, device):
        await self.client.connect()

        def wrap_protobuf(callback):
            async def wrapped(_, data):
                message = Update()
                message.ParseFromString(bytes(data))

                if all(s != Update.Signal.DISCONNECT for s in message.signals):
                    self.last_device = device
                    await self._disconnect_non_last()
                    await callback(message)
                else:
                    await self.client.disconnect()

            return wrapped

        await self.client.start_notify(PROTOBUF_OUTPUT, wrap_protobuf(self._on_protobuf))

    async def _disconnect_non_last(self):
        try:
            await self.scanner.stop()
        except AttributeError:
            # self.scanner is None sometimes and checking for that in an if before
            # calling scanner.stop doesn't work on Windows for some reason
            pass
        for device in self.found_devices:
            if device != self.last_device:
                client = BleakClient(device)
                await client.disconnect()

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
        pass

    def on_tap(self):
        pass

    def on_touch_down(self, x, y):
        pass

    def on_touch_up(self, x, y):
        pass

    def on_touch_move(self, x, y):
        pass

    def on_touch_cancel(self, x, y):
        pass

    def on_rotary(self, direction):
        pass

    def on_back_button(self):
        pass
