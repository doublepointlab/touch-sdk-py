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
