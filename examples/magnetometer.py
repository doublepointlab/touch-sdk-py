from touch_sdk import Watch
import logging
# Get helpful log info
logging.basicConfig(level=logging.INFO)

class MyWatch(Watch):

    def on_sensors(self, sensors):
        print(sensors.magnetic_field, sensors.magnetic_field_calibration)

    def on_tap(self):
        print('tap')

    def on_touch_down(self, x, y):
        print('touch down', x, y)

    def on_touch_up(self, x, y):
        print('touch up', x, y)

    def on_touch_move(self, x, y):
        print('touch move', x, y)

    def on_rotary(self, direction):
        print('rotary', direction)

    def on_back_button(self):
        self.trigger_haptics(1.0, 20)
        print('back button')

watch = MyWatch()
watch.start()
