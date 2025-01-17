from touch_sdk import Watch, GestureType
import logging

# Get helpful log info
logging.basicConfig(level=logging.INFO)


class MyWatch(Watch):

    # def on_sensors(self, sensors):
    #     print(sensors)

    def on_gesture(self, gesture):
        if gesture != GestureType.NONE:
            print("Gesture:", gesture)

    def on_touch_down(self, x, y):
        print("touch down", x, y)

    def on_touch_up(self, x, y):
        print("touch up", x, y)

    def on_touch_move(self, x, y):
        print("touch move", x, y)

    def on_rotary(self, direction):
        print("rotary", direction)

    def on_back_button(self):
        self.trigger_haptics(1.0, 20)
        print("back button")

    def on_connect(self):
        print(
            "Connected watch has name {}, app id {}, app version {}, manufacturer {}, and battery level {}".format(
                self.device_name,
                self.app_id,
                self.app_version,
                self.manufacturer,
                self.battery_percentage,
            )
        )
        print("Following models are available:")
        for i, m in enumerate(self.available_models):
            print("{}:".format(i), m)


watch = MyWatch()
watch.start()
