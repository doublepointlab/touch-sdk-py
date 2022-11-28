# Touch SDK py

Connects to Port 6 Touch SDK compatible Bluetooth devices – like [this WearOS app](https://play.google.com/store/apps/details?id=io.port6.watchbridge).

## Example usage
```
from touch_sdk import WatchManager

class MyWatchManager(WatchManager):
    def on_gyro(self, angular_velocity):
        print(angular_velocity)

wm = MyWatchManager()
wm.start()
```

## Usage

All callback functions should be methods in the class that inherits `WatchManager`, like in the example above.

### Tap gesture
```
def on_tap(self):
    print('tap')
```

### Acceleration
```
def on_acc(self, acceleration):
    print(acceleration)
```

### Angulary velocity / gyroscope
```
def on_gyro(self, angular_velocity):
    print(angular_velocity)
```

### Gravity vector
```
def on_grav(self, gravity_vector):
    print('gravity', gravity_vector)
```

### Orientation / quaternion
```
def on_quat(self, quaternion):
    print('quat', quaternion)
```

### Touch screen
```
def on_touch_down(self, x, y):
    print('touch down', x, y)

def on_touch_up(self, x, y):
    print('touch up', x, y)

def on_touch_move(self, x, y):
    print('touch move', x, y)
```

### Rotary dial
```
def on_rotary(self, direction):
    print('rotary', direction)
```
Outputs +1 for clockwise and -1 for counter-clockwise.

### Back button
```
def on_back_button(self):
    print('back button')
```
Called when the back button is pressed and released. WearOS does not support separate button down and button up events for the back button.

## Pylint
`python3 -m pylint src --rcfile=.pylintrc`