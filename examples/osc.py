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
        osc_client.send_message("/angular-velocity", angular_velocity)
        print(angular_velocity)

watch = MyWatch()
watch.start()
