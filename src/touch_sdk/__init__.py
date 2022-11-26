import asyncio
import struct

from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError


# GATT characteristic UUIDs

# These are found under the service with a
# service UUID of "4b574af0-72d7-45d2-a1bb-23cd0ec20c57"
ACC_UUID = '4b574af2-72d7-45d2-a1bb-23cd0ec20c57'
GYRO_UUID = '4b574af1-72d7-45d2-a1bb-23cd0ec20c57'
GRAV_UUID = '4b574af3-72d7-45d2-a1bb-23cd0ec20c57'
QUAT_UUID = '4b574af4-72d7-45d2-a1bb-23cd0ec20c57'

SERVICE_UUID = '008e74d0-7bb3-4ac5-8baf-e5e372cced76'

# These are found under the service with a
# service UUID of "008e74d0-7bb3-4ac5-8baf-e5e372cced76"
GESTURE_UUID = '008e74d1-7bb3-4ac5-8baf-e5e372cced76'
TOUCH_UUID = '008e74d2-7bb3-4ac5-8baf-e5e372cced76'
MOTION_UUID = '008e74d3-7bb3-4ac5-8baf-e5e372cced76'


TOUCH_TYPES = {0: "Down", 1: "Up", 2: "Move"}
MOTION_TYPES = {0: "Rotary", 1: "Back button"}
ROTARY_INFOS = {0: "clockwise", 1: "counterclockwise"}
GESTURES = {0: "None", 1: "Tap"}

class WatchManager:

    def __init__(self):
        self.found_devices = []
        self.last_device = None

    def start(self):
        asyncio.run(self.run())

    async def run(self):
        self.scanner = BleakScanner(self.detection_callback)
        await self.scanner.start()
        while True:
            await asyncio.sleep(1)

    async def detection_callback(self, device, advertisement_data):
        name = (advertisement_data.manufacturer_data.get(0xffff, bytearray()).decode("utf-8")
                or advertisement_data.local_name)

        if SERVICE_UUID in advertisement_data.service_uuids:
            if device in self.found_devices:
                return

            self.found_devices.append(device)

            client = BleakClient(device)
            if client.is_connected:
                return

            print(f"Found {name}")
            try:
                await self.do_connect(device)
            except asyncio.exceptions.CancelledError:
                print('connection cancelled from', name)
            except BleakError:
                pass

            if not 'gx5j' in name.lower():
                return
            # await scanner.stop()
            try:
                pass
                # await do_connect(device)
            except:
                pass
    
    async def do_connect(self, device):
        client = BleakClient(device)
        await client.connect()
        
        def wrapper(function):
            async def wrapped(_, data):
                self.last_device = device
                await self.disconnect_non_last()
                await function(_, data)
            return wrapped

        await client.start_notify(GYRO_UUID, wrapper(self.on_gyro))
        await client.start_notify(GRAV_UUID, wrapper(self.on_grav))
        await client.start_notify(ACC_UUID, wrapper(self.on_acc))
        await client.start_notify(QUAT_UUID, wrapper(self.on_quat))
        await client.start_notify(GESTURE_UUID, wrapper(self.on_gesture))
        await client.start_notify(TOUCH_UUID, wrapper(self.on_touch))
        await client.start_notify(MOTION_UUID, wrapper(self.on_motion))
    
    async def disconnect_non_last(self):
        print('Connected to', self.last_device)
        await self.scanner.stop()
        for device in self.found_devices:
            # print(device, self.last_device)
            if device != self.last_device:
                client = BleakClient(device)
                await client.disconnect()

    
    async def on_gyro(self, _, data):
        gyro = struct.unpack('>3f', data)
        print(f"angular velocity: {gyro}")


    async def on_acc(self, _, data):
        acc = struct.unpack('>3f', data)
        # print(f"acceleration: {acc}")

    async def on_grav(self, _, data):
        grav = struct.unpack('>3f', data)
        # print(f"gravity: {grav}")

    async def on_quat(self, _, data):
        quat = struct.unpack('>4f', data[:16])
        # print(f"orientation: {quat}")

    async def on_gesture(self, _, data):
        gesture = struct.unpack('>b', data)
        print(f"gesture: {GESTURES[gesture[0]]}")

    async def on_touch(self, _, data):
        touch = struct.unpack('>b2f', data)
        print(f"touch: {TOUCH_TYPES[touch[0]]}, x: {touch[1]}, y: {touch[2]}")

    async def on_motion(self, _, data):
        motion = struct.unpack('>2b', data)
        print(f"motion: {MOTION_TYPES[motion[0]]}", end="")
        print(f" {ROTARY_INFOS[motion[1]]}" if motion[0] == 0 else "")



if __name__ == "__main__":
    wm = WatchManager()
    wm.start()
