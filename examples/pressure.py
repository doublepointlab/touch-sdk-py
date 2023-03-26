from touch_sdk import Watch


class MyWatch(Watch):
    def on_pressure(self, pressure):
        print(f"Pressure: {pressure} hPa")


watch = MyWatch()
watch.start()
