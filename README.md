# Touch SDK py

Connects to Port 6 Touch SDK compatible Bluetooth devices – like [this WearOS app](https://play.google.com/store/apps/details?id=io.port6.watchbridge).

## Example usage
```
from touch_sdk import WatchManager

class MyWatchManager(WatchManager):
    def on_gyro(self, angularVelocity):
        print(angularVelocity)

wm = MyWatchManager()
wm.start()
```