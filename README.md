# Touch SDK py

![PyPI](https://img.shields.io/pypi/v/touch-sdk)
![PyPI - Downloads](https://img.shields.io/pypi/dm/touch-sdk)
![PyPI - License](https://img.shields.io/pypi/l/touch-sdk)
![Discord](https://img.shields.io/discord/869474617729875998)

Connects to Doublepoint Touch SDK compatible Bluetooth devices – like [this Wear OS app](https://play.google.com/store/apps/details?id=io.port6.watchbridge).

There is also a [web SDK](https://www.npmjs.com/package/touch-sdk) and a [Unity SDK](https://openupm.com/packages/io.port6.sdk/).

See [doublepoint.com/product](https://doublepoint.com/product) for more info.

## Installation

```sh
pip install touch-sdk
```

## Example usage
```python
from touch_sdk import Watch

class MyWatch(Watch):
    def on_tap(self):
        print('Tap')

watch = MyWatch()
watch.start()
```

## Usage

All callback functions should be methods in the class that inherits `Watch`, like in the example above.

An optional name string in the constructor will search only for devices with that name (case insensitive).

```python
watch = MyWatch('fvaf')
```

### Tap gesture
```python
def on_tap(self):
    print('tap')
```

### Sensors
```python
def on_sensors(self, sensors):
    print(sensors.acceleration) # (x, y, z)
    print(sensors.gravity) # (x, y, z)
    print(sensors.angular_velocity) # (x, y, z)
    print(sensors.orientation) # (x, y, z, w)
    print(sensors.magnetic_field) # (x, y, z), or None if unavailable
    print(sensors.magnetic_field_calibration) # (x, y, z), or None if unavailable
```

### Touch screen
```python
def on_touch_down(self, x, y):
    print('touch down', x, y)

def on_touch_up(self, x, y):
    print('touch up', x, y)

def on_touch_move(self, x, y):
    print('touch move', x, y)

def on_touch_cancel(self, x, y):
    print('touch cancel', x, y)
```

### Rotary dial
```python
def on_rotary(self, direction):
    print('rotary', direction)
```
Outputs +1 for clockwise and -1 for counter-clockwise.

### Back button
```python
def on_back_button(self):
    print('back button')
```

Called when the back button is pressed and released. Wear OS does not support separate button down and button up events for the back button.

### Tap Gestures
The SDK supports detecting single taps, double taps, and triple taps. Here's how to implement them:

```python
from touch_sdk import Watch
import time

class MyWatch(Watch):
    def __init__(self):
        super().__init__()
        self.last_tap_time = 0
        self.tap_count = 0
        self.tap_timeout = 0.5  # Time window for multi-taps (in seconds)

    def on_tap(self):
        current_time = time.time()
        
        # Reset tap count if too much time has passed
        if current_time - self.last_tap_time > self.tap_timeout:
            self.tap_count = 0
        
        self.tap_count += 1
        self.last_tap_time = current_time

        # Process taps after a short delay
        if self.tap_count == 1:
            # Schedule single tap check
            self._schedule_tap_check()
        elif self.tap_count == 2:
            print("Double tap detected!")
        elif self.tap_count == 3:
            print("Triple tap detected!")
            self.tap_count = 0  # Reset after triple tap

    async def _schedule_tap_check(self):
        await asyncio.sleep(self.tap_timeout)
        if self.tap_count == 1:
            print("Single tap detected!")
            self.tap_count = 0

### OSC Integration
The SDK provides OSC (Open Sound Control) integration for streaming data from watches to other applications. You can connect multiple watches simultaneously by using different ports.

```python
from touch_sdk import Watch
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient
import threading

class OSCWatch(Watch):
    def __init__(self, ip, client_port, server_port, name_filter=None):
        super().__init__(name_filter)
        # OSC client for sending data
        self.osc_client = SimpleUDPClient(ip, client_port)
        
        # OSC server for receiving commands
        self.dispatcher = Dispatcher()
        self.dispatcher.map("/vib/intensity", self.handle_intensity)
        self.dispatcher.map("/vib/duration", self.handle_duration)
        self.server = ThreadingOSCUDPServer((ip, server_port), self.dispatcher)
        
        self.intensity_value = 0
        self.duration_value = 0

    def start_osc_server(self):
        server_thread = threading.Thread(target=self.server.serve_forever)
        server_thread.start()

    def on_sensors(self, sensors):
        # Stream sensor data via OSC
        self.osc_client.send_message("/angular-velocity", sensors.angular_velocity)
        self.osc_client.send_message("/gravity", sensors.gravity)
        self.osc_client.send_message("/acceleration", sensors.acceleration)
        self.osc_client.send_message("/orientation", sensors.orientation)
        self.osc_client.send_message("/magnetic-field", sensors.magnetic_field)

    def handle_intensity(self, address, *args):
        self.intensity_value = args[0] if args else None
        if self.intensity_value and self.duration_value:
            self.trigger_haptics(self.intensity_value, self.duration_value)

    def handle_duration(self, address, *args):
        self.duration_value = args[0] if args else None
        if self.intensity_value and self.duration_value:
            self.trigger_haptics(self.intensity_value, self.duration_value)
```

To connect multiple watches simultaneously, use different port numbers for each watch:

```python
# First watch
watch1 = OSCWatch(
    ip="127.0.0.1",
    client_port=6661,  # Port for sending data
    server_port=6671   # Port for receiving commands
)
watch1.start_osc_server()

# Second watch
watch2 = OSCWatch(
    ip="127.0.0.1",
    client_port=6662,  # Different port for second watch
    server_port=6672   # Different port for second watch
)
watch2.start_osc_server()
```

The OSC integration supports:
- Streaming sensor data (acceleration, gravity, orientation, etc.)
- Receiving haptic feedback commands
- Sending touch events, taps, and rotary input
- Real-time communication with multiple watches

See `examples/osc_client_server_6661.py` and `examples/osc_client_server_6662.py` for complete implementations.

### Flick Gestures
The SDK provides a FlickDetector class that can detect flick gestures in different directions after a tap. See `examples/flick.py` for a complete implementation.

```python
from touch_sdk.examples.flick import FlickDetector, Flick

class MyWatch(Watch):
    def __init__(self):
        super().__init__()
        # Customize flick detection parameters
        self.flick_detector = FlickDetector(
            flick_initiation_threshold=30.0,  # Minimum movement to trigger a flick
            flick_delay_ms=100,              # Time window after tap to detect flick
            flick_min_interval=300,          # Minimum time between flicks
            scale=6.0,                       # Movement scaling factor
            update_interval=2.0              # Sensor update interval
        )

    def on_tap(self):
        self.flick_detector.on_tap()

    def on_sensors(self, sensors):
        self.flick_detector.update()
        self.flick_detector.on_sensors(sensors)
        gesture = self.flick_detector.get()
        if gesture:
            if gesture == Flick.Up:
                print("Flicked Up!")
            elif gesture == Flick.Down:
                print("Flicked Down!")
            elif gesture == Flick.Left:
                print("Flicked Left!")
            elif gesture == Flick.Right:
                print("Flicked Right!")
            elif gesture == Flick.Tap:
                print("Just a Tap!")
```

### Probability output
```python
def on_gesture_probability(self, probabilities):
    print(f'probabilities: {probabilities}')
```
Triggered when a gesture detection model produces an output. See `examples/pinch_probability.py` for a complete example.

### Haptics
The `trigger_haptics(intensity, length)` method can be used to initiate one-shot haptic effects on the watch. For example, to drive the haptics motor for 300 ms at 100% intensity on `watch`, call `watch.trigger_haptics(1.0, 300)`.

### Miscellaneous
```python
watch.hand # Hand.NONE, Hand.LEFT or Hand.RIGHT
watch.battery_percentage # 0-100
watch.touch_screen_resolution # (width, height) or None
watch.haptics_available # True if device supports haptic feedback
```

## Acting as backend for Unity Play Mode

This package provides the `stream_watch` module, which makes it possible to use touch-sdk-py as the backend for touch-sdk-unity (>=0.12.0) applications in Play Mode. To use this feature, create a virtual environment in which touch-sdk-py is installed, and then set the python path of the `BluetoothWatchProvider` script in your Unity project to the virtual environment's python executable.

## Unexplainable bugs
Sometimes turning your device's Bluetooth off and on again fixes problems – this has been observed on Linux, Mac and Windows. This is unideal, but those error states are hard to reproduce and thus hard to fix.

## Pylint
```sh
python3 -m pylint src --rcfile=.pylintrc
```

### Adding pylint to pre-commit
```sh
echo 'python3 -m pylint src --rcfile=.pylintrc -sn' > .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```
