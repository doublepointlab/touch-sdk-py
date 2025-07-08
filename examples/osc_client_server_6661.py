import asyncio
import threading
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient
from touch_sdk import Watch
import logging
# Get helpful log info
logging.basicConfig(level=logging.INFO)


class MyWatch(Watch):
    def __init__(self, ip, client_port, server_port, name_filter=None):
        super().__init__(name_filter)
        self.osc_client = SimpleUDPClient(ip, client_port)
        self.dispatcher = Dispatcher()
        self.dispatcher.map("/vib/intensity", self.handle_intensity)
        self.dispatcher.map("/vib/duration", self.handle_duration)

        self.server = ThreadingOSCUDPServer((ip, server_port), self.dispatcher)
        print(f"OSC server serving on {ip}:{server_port}")

        self.intensity_value = 0
        self.duration_value = 0

    def handle_intensity(self, address, *args):
        self.intensity_value = args[0] if args else None
        if self.intensity_value and self.duration_value:
            self.trigger_haptics(self.intensity_value, self.duration_value)

    def handle_duration(self, address, *args):
        self.duration_value = args[0] if args else None
        if self.intensity_value and self.duration_value:
            self.trigger_haptics(self.intensity_value, self.duration_value)

    def start_osc_server(self):
        server_thread = threading.Thread(target=self.server.serve_forever)
        server_thread.start()

    def stop_osc_server(self):
        self.server.shutdown()

    def on_sensors(self, sensors):
        self.osc_client.send_message("/angular-velocity", sensors.angular_velocity)
        self.osc_client.send_message("/gravity", sensors.gravity)
        self.osc_client.send_message("/acceleration", sensors.acceleration)
        self.osc_client.send_message("/orientation", sensors.orientation)
        self.osc_client.send_message("/magnetic-field", sensors.magnetic_field)

    async def send_tap_zero_later(self):
        await asyncio.sleep(0.1)
        self.osc_client.send_message("/tap", 0)
        print('tap 0')

    def on_tap(self):
        self.osc_client.send_message("/tap", 1)
        print('tap 1')
        # Schedule the sending of /tap 0 message half a second later
        asyncio.ensure_future(self.send_tap_zero_later())

    def on_touch_down(self, x, y):
        self.osc_client.send_message("/touch-down", [x, y])
        print('touch down', x, y)

    def on_touch_up(self, x, y):
        self.osc_client.send_message("/touch-up", [x, y])
        print('touch up', x, y)

    def on_touch_move(self, x, y):
        self.osc_client.send_message("/touch-move", [x, y])
        print('touch move', x, y)

    def on_rotary(self, direction):
        self.osc_client.send_message("/rotary", direction)
        print('rotary', direction)

    async def send_back_button_zero_later(self):
        await asyncio.sleep(0.1)
        self.osc_client.send_message("/back-button", 0)
        print('back button 0')

    def on_back_button(self):
        self.osc_client.send_message("/back-button", 1)
        self.trigger_haptics(1.0, 20)
        print('back button 1')
        # Schedule the sending of /back-button 0 message half a second later
        asyncio.ensure_future(self.send_back_button_zero_later())

# Setup the IP, client port (for sending), and server port (for receiving)
ip = "127.0.0.1"
client_port = 6661
server_port = 6671

# Create an instance of MyWatch
watch = MyWatch(ip, client_port, server_port)

# Start the OSC server
watch.start_osc_server()

async def main():
    try:
        # Start the watch
        await watch.run()
    except KeyboardInterrupt:
        print("Exiting...")

# Run the program using asyncio's event loop
loop = asyncio.get_event_loop()
try:
    loop.run_until_complete(main())
    # Optionally, if you need to await the completion of all tasks:
    pending = asyncio.all_tasks(loop)
    loop.run_until_complete(asyncio.gather(*pending))

    watch.stop_osc_server()  # Stop the OSC server
    loop.close()
except KeyboardInterrupt:
    pass
finally:
    watch.stop()  # Stop the Touch SDK Watch
    watch.stop_osc_server()  # Stop the OSC server
    loop.close()
