import asyncio

from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError
import asyncio_atexit

class MultiConnectionClient:
    def __init__(self, service_uuid):
        self.service_uuid = service_uuid
        self.scanner = None
        self.devices = {}

    def start(self):
        try:
            asyncio.run(self.run())
        except KeyboardInterrupt:
            pass

    async def run(self):
        asyncio_atexit.register(self.stop)
        self.scanner = BleakScanner(
            self._detection_callback, service_uuids=[self.service_uuid]
        )
        await self.scanner.start()
        print('Scanning...')
        while True:
            await asyncio.sleep(1)

    async def stop(self):
        await self.disconnect_devices()

    async def _detection_callback(self, device, advertisement_data):
        name = (
            advertisement_data.manufacturer_data.get(0xFFFF, bytearray()).decode(
                "utf-8"
            )
            or advertisement_data.local_name
        )

        if self.service_uuid in advertisement_data.service_uuids:
            if device in self.devices:
                return

            client = BleakClient(device)

            if client.is_connected:
                return

            print(f"Found {name}")
            self.devices.update({device: client})

            try:
                await client.connect()
                await self.handle_connect(device)
            except asyncio.exceptions.CancelledError:
                print("Connection cancelled from", name)
            except BleakError:
                pass
    
    async def handle_connect(self, device):
        pass

    async def disconnect_devices(self, exclude=None):
        try:
            await self.scanner.stop()
        except AttributeError:
            # self.scanner is None sometimes and checking for that in an if before
            # calling scanner.stop doesn't work on Windows for some reason
            pass

        for device in self.devices:
            if device != exclude:
                client = self.devices[device]
                await client.disconnect()