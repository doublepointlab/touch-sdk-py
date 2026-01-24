# Touch SDK py

![PyPI](https://img.shields.io/pypi/v/touch-sdk)
![PyPI - Downloads](https://img.shields.io/pypi/dm/touch-sdk)
![PyPI - License](https://img.shields.io/pypi/l/touch-sdk)
![Discord](https://img.shields.io/discord/869474617729875998)

Connects to Doublepoint Touch SDK compatible Bluetooth devices – like [this Wear OS app](https://play.google.com/store/apps/details?id=io.port6.watchbridge).

There is also a [JavaScript SDK](https://www.npmjs.com/package/touch-sdk) and a [Unity SDK](https://openupm.com/packages/io.port6.sdk/).

See [docs.doublepoint.com](https://docs.doublepoint.com/docs/touch-sdk) for more info.

## Installation

```sh
pip install touch-sdk
```

## Quick Setup (recommended)

[![Setup Tutorial](scripts/doublepoint_touchsdk_py_oneshot_setup.png)](scripts/doublepoint_touchsdk_py_oneshot_setup.mp4)

*👆 Click image to watch setup video*

One command to set up Python 3.11, venv, and all dependencies:

**macOS / Linux:**
```sh
bash scripts/oneshot_setup_cursor.sh
```

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\oneshot_setup.ps1
```

After setup, run examples:

**macOS / Linux:**
```sh
python examples/basic.py
python examples/osc_client_server.py
python examples/plotter.py
```

**Windows:**
```batch
scripts\run_osc_bridge.bat
```
Or activate the venv manually and run Python:
```batch
.venv\Scripts\activate
python examples\osc_client_server.py
```

## Example Usage

```python
from touch_sdk import Watch, GestureType

class MyWatch(Watch):
    def on_gesture(self, gesture):
        if gesture == GestureType.PINCH_TAP:
            print('Tap')

watch = MyWatch()
watch.start()
```


## API Reference

All callbacks are methods in a class that inherits `Watch`.

Optional name filter (case insensitive):
```python
watch = MyWatch('device-name')
```

### Gestures (Tap, Swipe, Hold, etc.)
```python
from touch_sdk import GestureType

def on_gesture(self, gesture):
    if gesture == GestureType.DPAD_LEFT:
        print('swipe left')
    elif gesture == GestureType.DPAD_RIGHT:
        print('swipe right')
    elif gesture == GestureType.PINCH_HOLD:
        print('hold')
    elif gesture == GestureType.PINCH_TAP:
        print('tap')
```

Note: Swipe and Hold require different gesture models. Switch via watch menu or right hardware button.

### Gesture Probability
```python
def on_gesture_probability(self, probabilities):
    print(probabilities)  # dict of GestureType -> float (0-1)
```

### Sensors
```python
def on_sensors(self, sensors):
    print(sensors.acceleration)    # (x, y, z)
    print(sensors.gravity)         # (x, y, z)
    print(sensors.angular_velocity) # (x, y, z)
    print(sensors.orientation)     # (x, y, z, w)
```

### Touch Screen
```python
def on_touch_down(self, x, y):
    print('touch down', x, y)

def on_touch_up(self, x, y):
    print('touch up', x, y)

def on_touch_move(self, x, y):
    print('touch move', x, y)
```

### Rotary Dial
```python
def on_rotary(self, direction):
    print('rotary', direction)  # +1 clockwise, -1 counter-clockwise
```

### Back Button
```python
def on_back_button(self):
    print('back button')
```

### Haptics
```python
watch.trigger_haptics(1.0, 300)  # intensity (0-1), duration (ms)
```

### Properties
```python
watch.hand                    # Hand.NONE, Hand.LEFT, Hand.RIGHT
watch.battery_percentage      # 0-100
watch.touch_screen_resolution # (width, height) or None
watch.haptics_available       # True if supported
```

### Connecting to a Specific Watch

By default, the SDK connects to the first available watch. To connect to a specific watch by name:

**In code:**
```python
watch = MyWatch('My Watch Name')  # case insensitive
```

**OSC bridge (command line):**
```sh
python examples/osc_client_server.py --name-filter "My Watch Name"
```

**Windows batch file:**
```batch
scripts\run_osc_bridge.bat --name-filter "My Watch Name"
```

The name filter matches any watch whose name contains the given string (case insensitive).

**Tip:** The watch ID is displayed on the DevKit screen.

### Multiple Watches

To connect multiple watches simultaneously, run separate instances with different ports and name filters:

```sh
python examples/osc_client_server.py --name-filter "Watch A" --client-port 6666 --server-port 6667
python examples/osc_client_server.py --name-filter "Watch B" --client-port 6668 --server-port 6669
```


## Unity Backend

The `stream_watch` module can serve as backend for touch-sdk-unity (>=0.12.0) in Play Mode. Set the python path in `BluetoothWatchProvider` to your venv's python executable.

## Troubleshooting

If things don't work, try turning Bluetooth off and on again. This fixes many issues on Linux, Mac, and Windows.

### Unpairing the DevKit

To unpair and reset Bluetooth on the Doublepoint DevKit:

1. **Press both buttons** simultaneously to open the menu
2. **Navigate** using the left button until you reach **BL MODE**
3. **Select** with the right button
4. **Select Unpair** with the right button

After unpairing, the DevKit will be discoverable again for new connections.

