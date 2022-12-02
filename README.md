# Touch SDK py

Connects to Port 6 Touch SDK compatible Bluetooth devices – like [this Wear OS app](https://play.google.com/store/apps/details?id=io.port6.watchbridge).

There is also a [web SDK](https://www.npmjs.com/package/touch-sdk) and a [Unity SDK](https://openupm.com/packages/io.port6.sdk/).

See [port6.io/sdk](https://port6.io/sdk/) for more info.

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
    print(sensors.acceleration) # x, y, z
    print(sensors.gravity) # x, y, z
    print(sensors.angular_velocity) # x, y, z
    print(sensors.orientation) # x, y, z, w
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

## Pylint
```sh
python3 -m pylint src --rcfile=.pylintrc
```

### Adding pylint to pre-commit
```sh
echo 'python3 -m pylint src --rcfile=.pylintrc -sn' > .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```