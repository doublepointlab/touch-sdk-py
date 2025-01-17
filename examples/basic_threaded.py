from threading import Thread
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


watch = MyWatch()
thread = Thread(target=watch.start)
thread.start()
input("Press enter to exit\n")
watch.stop()
thread.join()
