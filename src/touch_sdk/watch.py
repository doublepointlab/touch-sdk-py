from dataclasses import dataclass
from enum import Enum, IntEnum
import asyncio
from typing import Tuple, Optional
import asyncio_atexit

from touch_sdk.uuids import PROTOBUF_OUTPUT, PROTOBUF_INPUT
from touch_sdk.utils import unpack_chained
from touch_sdk.watch_connector import WatchConnector

# pylint: disable=no-name-in-module
from touch_sdk.protobuf.common_pb2 import GestureType as ProtoGestureType, Model
from touch_sdk.protobuf.watch_output_pb2 import Update, TouchEvent
from touch_sdk.protobuf.watch_input_pb2 import InputUpdate, HapticEvent


__doc__ = """Discovering Touch SDK compatible BLE devices and interfacing with them."""


class GestureType(IntEnum):
    NONE = ProtoGestureType.NONE
    PINCH_TAP = ProtoGestureType.PINCH_TAP
    CLENCH = ProtoGestureType.CLENCH
    SURFACE_TAP = ProtoGestureType.SURFACE_TAP
    PINCH_HOLD = ProtoGestureType.PINCH_HOLD
    DPAD_LEFT = ProtoGestureType.DPAD_LEFT
    DPAD_RIGHT = ProtoGestureType.DPAD_RIGHT
    DPAD_UP = ProtoGestureType.DPAD_UP
    DPAD_DOWN = ProtoGestureType.DPAD_DOWN


@dataclass(frozen=True)
class SensorFrame:
    """A Frozen container class for values of all streamable Touch SDK sensors."""

    acceleration: Tuple[float, float, float]
    gravity: Tuple[float, float, float]
    angular_velocity: Tuple[float, float, float]
    orientation: Tuple[float, float, float, float]
    magnetic_field: Optional[Tuple[float, float, float]]
    magnetic_field_calibration: Optional[Tuple[float, float, float]]
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

        Optional name_filter connects only to watches with that name (case insensitive)
        """
        self._connector = WatchConnector(
            self._on_approved_connection, self._on_protobuf, name_filter
        )

        self._client = None
        self._stop_event = None

        self._event_loop = None

        self.custom_data = None
        if hasattr(self.__class__, "custom_data"):
            self.custom_data = self.__class__.custom_data

        self._hand = Hand.NONE
        self._battery_percentage = -1

        self._screen_resolution = None
        self._haptics_available = False

        self._app_version = ""
        self._app_id = ""
        self._device_name = ""
        self._manufacturer = ""
        self._model_info = ""

        self._available_models: list[set[GestureType]] = []
        self._active_model: set[GestureType] = {}

    @property
    def hand(self) -> Hand:
        """Which hand the device is worn on."""
        return self._hand

    @property
    def battery_percentage(self) -> int:
        """Last known battery percentage of the device."""
        return self._battery_percentage

    @property
    def touch_screen_resolution(self) -> Optional[Tuple[int, int]]:
        """Resolution of the touch screen (width, height) in pixels.
        None if not fetched, or no touch screen is available."""
        return self._screen_resolution

    @property
    def haptics_available(self) -> bool:
        """Whether the device supports haptic feedback."""
        return self._haptics_available

    @property
    def app_version(self) -> str:
        """Version of the software running on the device."""
        return self._app_version

    @property
    def app_id(self) -> str:
        """Identifier of the software running on the device."""
        return self._app_id

    @property
    def device_name(self) -> str:
        """Type name of the device."""
        return self._device_name

    @property
    def manufacturer(self) -> str:
        """Manufacturer of the device."""
        return self._manufacturer

    @property
    def model_info(self) -> str:
        """Miscellaneous info about the gesture detection model."""
        return self._model_info

    @property
    def available_models(self) -> list[set[GestureType]]:
        """Available models by predicted gestures"""
        return self._available_models

    @property
    def active_model(self) -> set[GestureType]:
        """Active model by predicted gestures"""
        return self._active_model

    def start(self):
        """Blocking event loop that starts the Bluetooth scanner

        More handy than Watch.run when only this event loop is needed."""
        try:
            asyncio.run(self.run())
        except KeyboardInterrupt:
            pass

    def stop(self):
        """Stop the watch, disconnecting any connected devices."""
        self._stop_event.set()

    async def run(self):
        """Asynchronous blocking event loop that starts the Bluetooth scanner.

        Makes it possible to run multiple async event loops with e.g. asyncio.gather."""

        self._event_loop = asyncio.get_running_loop()
        self._stop_event = asyncio.Event()

        asyncio_atexit.register(self.stop)

        await self._connector.start()
        await self._stop_event.wait()
        await self._connector.stop()

    def on_sensors(self, sensor_frame: SensorFrame):
        """Callback when accelerometer, gyroscope, gravity, orientation, and
        magnetic field are changed. Guaranteed to have values for everything but
        magnetic field information in every update."""

    def on_arm_direction_change(self, delta_x: float, delta_y: float):
        """Gyroscope-based raycasting output. Called after sensor updates."""

    def on_pressure(self, pressure: float):
        """Called when new pressure value (in hectopascals) is received."""

    def on_gesture_probability(self, probabilities: dict[GestureType, float]):
        """Called when gesture probability is received."""

    def on_tap(self):
        """Called when a pinch tap gesture happens."""

    def on_gesture(self, gesture: GestureType):
        """Called when gesture info is received. May receive GestureType.NONE."""

    def on_touch_down(self, x: float, y: float):
        """Touch screen touch starts."""

    def on_touch_up(self, x: float, y: float):
        """Touch screen touch ends."""

    def on_touch_move(self, x: float, y: float):
        """Touch screen touch moves."""

    def on_touch_cancel(self, x: float, y: float):
        """Touch screen touch becomes a swipe gesture that goes to another view."""

    def on_back_button(self):
        """Back button of the watch is pressed and released.

        Wear OS does not support separate button down and button up events."""

    def on_rotary(self, direction: int):
        """Rotary dial around the watch screen is turned.

        direction: +1 for clockwise, -1 for counterclockwise."""

    def on_custom_data(self, uuid: str, content: Tuple):
        """Receive data from custom characteristics"""

    def on_connect(self):
        """Called after watch has connected"""

    def on_info_update(self):
        """Called if info properties are updated"""

    def trigger_haptics(self, intensity: float, duration_ms: int):
        """Trigger vibration haptics on the watch.

        intensity: between 0 and 1
        duration_ms: between 0 and 5000"""
        input_update = self._create_haptics_update(intensity, duration_ms)
        self._write_input_characteristic(input_update.SerializeToString(), self._client)

    def request_model(self, gestures: set[GestureType]):
        model = self._create_model_request(gestures)
        self._write_input_characteristic(model.SerializeToString(), self._client)

    # IMPLEMENTATION DETAILS

    @staticmethod
    def _protovec2_to_tuple(vec):
        return (vec.x, vec.y)

    @staticmethod
    def _protovec3_to_tuple(vec):
        return (vec.x, vec.y, vec.z)

    @staticmethod
    def _protoquat_to_tuple(vec):
        return (vec.x, vec.y, vec.z, vec.w)

    async def _on_approved_connection(self, client):
        self._client = client

        await self._fetch_info(client)
        await self._subscribe_to_custom_characteristics(client)

        self.on_connect()

    async def _fetch_info(self, client):
        data = await client.read_gatt_char(PROTOBUF_OUTPUT)
        update = Update()
        update.ParseFromString(bytes(data))
        if update.HasField("info"):
            self._proto_on_info(update.info)

    # Custom characteristics

    async def _subscribe_to_custom_characteristics(self, client):
        if self.custom_data is None:
            return

        subscriptions = [
            client.start_notify(uuid, self._on_custom_data) for uuid in self.custom_data
        ]
        await asyncio.gather(*subscriptions)

    async def _on_custom_data(self, characteristic, data):
        format_string = (self.custom_data or {}).get(characteristic.uuid)

        if format_string is None:
            return

        content = unpack_chained(format_string, data)

        self.on_custom_data(characteristic.uuid, content)

    async def _on_protobuf(self, message):
        # Main protobuf characteristic
        probs = {k.label: k.probability for k in message.probabilities}
        self.on_gesture_probability(probs)

        self._proto_on_sensors(message.sensorFrames, message.unixTime)
        self._proto_on_gestures(message.gestures)
        self._proto_on_touch_events(message.touchEvents)
        self._proto_on_button_events(message.buttonEvents)
        self._proto_on_rotary_events(message.rotaryEvents)

        if message.HasField("info"):
            self._proto_on_info(message.info)

        if message.pressure != 0.0:
            self.on_pressure(message.pressure)

    def _proto_on_sensors(self, frames, timestamp):
        # Sensor events
        frame = frames[-1]
        sensor_frame = SensorFrame(
            acceleration=Watch._protovec3_to_tuple(frame.acc),
            gravity=Watch._protovec3_to_tuple(frame.grav),
            angular_velocity=Watch._protovec3_to_tuple(frame.gyro),
            orientation=Watch._protoquat_to_tuple(frame.quat),
            magnetic_field=(
                Watch._protovec3_to_tuple(frame.mag) if frame.HasField("mag") else None
            ),
            magnetic_field_calibration=(
                Watch._protovec3_to_tuple(frame.magCal)
                if frame.HasField("magCal")
                else None
            ),
            timestamp=timestamp,
        )
        self.on_sensors(sensor_frame)
        self._on_arm_direction_change(sensor_frame)

    def _on_arm_direction_change(self, sensor_frame: SensorFrame):
        def normalize(vector):
            length = sum(x * x for x in vector) ** 0.5
            return [x / length for x in vector]

        grav = normalize(sensor_frame.gravity)

        av_x = -sensor_frame.angular_velocity[2]  # right = +
        av_y = -sensor_frame.angular_velocity[1]  # down = +

        handedness_scale = -1 if self._hand == Hand.LEFT else 1

        delta_x = av_x * grav[2] + av_y * grav[1]
        delta_y = handedness_scale * (av_y * grav[2] - av_x * grav[1])

        self.on_arm_direction_change(delta_x, delta_y)

    def _proto_on_gestures(self, gestures):
        # Gestures
        if not gestures:
            self.on_gesture(GestureType.NONE)
        else:
            for g in gestures:
                if g.type == GestureType.PINCH_TAP:
                    self.on_tap()

                self.on_gesture(GestureType(g.type))

    def _proto_on_touch_events(self, touch_events):
        # Touch screen
        for touch in touch_events:
            coords = Watch._protovec2_to_tuple(touch.coords[0])
            if touch.eventType == TouchEvent.TouchEventType.BEGIN:
                self.on_touch_down(*coords)
            elif touch.eventType == TouchEvent.TouchEventType.END:
                self.on_touch_up(*coords)
            elif touch.eventType == TouchEvent.TouchEventType.MOVE:
                self.on_touch_move(*coords)
            elif touch.eventType == TouchEvent.TouchEventType.CANCEL:
                self.on_touch_cancel(*coords)

    def _proto_on_button_events(self, buttons):
        # Button
        if any(b.id == 0 for b in buttons):
            self.on_back_button()

    def _proto_on_rotary_events(self, rotary_events):
        # Rotary
        for rotary in rotary_events:
            self.on_rotary(-rotary.step)

    def _proto_on_info(self, info):
        # Info
        if battery_percentage := info.batteryPercentage:
            self._battery_percentage = battery_percentage

        if (hand := Hand(info.hand)) != Hand.NONE:
            self._hand = hand
        else:
            # If hand is not present, only battery is updated
            return

        if (screen_resolution := info.touchScreenResolution) is not None:
            self._screen_resolution = (screen_resolution.x, screen_resolution.y)

        if haptics_available := info.hapticsAvailable:
            self._haptics_available = haptics_available

        if app_version := info.appVersion:
            self._app_version = app_version

        if app_id := info.appId:
            self._app_id = app_id

        if device_name := info.deviceName:
            self._device_name = device_name

        if manufacturer := info.manufacturer:
            self._manufacturer = manufacturer

        if active_model := info.activeModel:
            self._active_model = set(
                map(lambda g: GestureType(g), active_model.gestures)
            )

        if available_models := info.availableModels:
            self._available_models = [
                set(map(lambda g: GestureType(g), g.gestures)) for g in available_models
            ]

        if model_info := info.modelInfo:
            self._model_info = model_info

        self.on_info_update()

    @staticmethod
    def _create_haptics_update(intensity, length):
        # Haptics
        clamped_intensity = min(max(intensity, 0.0), 1.0)
        clamped_length = min(max(int(length), 0), 5000)
        haptic_event = HapticEvent()
        haptic_event.type = HapticEvent.HapticType.ONESHOT
        haptic_event.length = clamped_length
        haptic_event.intensity = clamped_intensity
        input_update = InputUpdate()
        input_update.hapticEvent.CopyFrom(haptic_event)
        return input_update

    @staticmethod
    def _create_model_request(gestures: set[GestureType]):
        model = Model()
        model.gestures.extend(int(g) for g in gestures)
        input_update = InputUpdate()
        input_update.modelRequest.CopyFrom(model)
        return input_update

    def _write_input_characteristic(self, data, client):
        if self._event_loop is not None:
            self._event_loop.create_task(
                self._async_write_input_characteristic(PROTOBUF_INPUT, data, client)
            )

    async def _async_write_input_characteristic(self, characteristic, data, client):
        if client:
            await client.write_gatt_char(characteristic, data, True)
