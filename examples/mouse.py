# To use this example, make sure to install extra dependencies:
# pip install pyautogui
from touch_sdk import Watch
import pyautogui

class MouseWatch(Watch):

    scale = 30
    pinch_state = False

    def on_gesture_probability(self, prob):
        if prob >= 0.5 and not self.pinch_state:
            self.pinch_state = True
            pyautogui.mouseDown(_pause=False)
        elif prob < 0.5 and self.pinch_state:
            self.pinch_state = False
            pyautogui.mouseUp(_pause=False)

    def on_arm_direction_change(self, delta_x: float, delta_y: float):

        pyautogui.moveRel(
            self.scale * delta_x,
            self.scale * delta_y,
            _pause=False
        )


watch = MouseWatch()
watch.start()
