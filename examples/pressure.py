from touch_sdk import Watch
import logging
# Get helpful log info
logging.basicConfig(level=logging.INFO)


class MyWatch(Watch):
    def on_pressure(self, pressure):
        print(f"Pressure: {pressure} hPa")


watch = MyWatch()
watch.start()
