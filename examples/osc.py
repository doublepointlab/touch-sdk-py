# To use this example, make sure to install python-osc:
# pip install python-osc

from touch_sdk import Watch
from pythonosc.udp_client import SimpleUDPClient

ip = "127.0.0.1"
port = 6666

osc_client = SimpleUDPClient(ip, port)

class MyWatch(Watch):
    def on_sensors(self, sensors):
        angular_velocity = sensors.angular_velocity
        gravity = sensors.gravity
        acceleration = sensors.acceleration
        orientation = sensors.orientation
        osc_client.send_message("/angular-velocity", angular_velocity)
        osc_client.send_message("/gravity", gravity)
        osc_client.send_message("/acceleration", acceleration)
        osc_client.send_message("/orientation", orientation)        

    def on_tap(self):
        osc_client.send_message("/tap", 1)
        print('tap')

    def on_touch_down(self, x, y):
        osc_client.send_message("/touch-down", [x, y])
        print('touch down', x, y)

    def on_touch_up(self, x, y):
        osc_client.send_message("/touch-up", [x, y])
        print('touch up', x, y)

    def on_touch_move(self, x, y):
        osc_client.send_message("/touch-move", [x, y])
        print('touch move', x, y)

    def on_rotary(self, direction):
        osc_client.send_message("/rotary", direction)
        print('rotary', direction)

    def on_back_button(self):
        osc_client.send_message("/back-button", 1)
        self.trigger_haptics(1.0, 20)
        print('back button')

watch = MyWatch()
watch.start()
