import asyncio

from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError
import asyncio_atexit

__doc__ = """Scans for Bluetooth devices with a given GATT service UUID and connects
to all of them."""

class BLEConnector:
    """Scans for Bluetooth devices with service_uuid and connects to
    all of them. Also handles disconnects.

    connection_handler gets called every time the scanner finds a new device.
    It should take parameters device and name.

    If name_filter is present, only devices with that name will be connected to."""

    def __init__(self, connection_handler, service_uuid, name_filter=None):
        """Creates a new instance of BLEConnector. Does not start the scanning."""
        self.handle_connect = connection_handler
        self.service_uuid = service_uuid
        self.name_filter = name_filter
        self.scanner = None
        self.devices = {}

    def start(self):
        """Blocking event loop that starts the scanner. This is the easiest way
        to enter the scanning loop.

        Calls BLEConnector.run."""
        try:
            asyncio.run(self.run())
        except KeyboardInterrupt:
            pass

    async def run(self):
        """Blocking async event loop that starts the scanner.

        Useful when there are multiple async event loops in the program that
        need to be run at the same time."""
        asyncio_atexit.register(self.stop)
        self.scanner = BleakScanner(
            self._detection_callback, service_uuids=[self.service_uuid]
        )
        await self.scanner.start()
        print('Scanning...')
        while True:
            await asyncio.sleep(1)

    async def stop(self):
        """Stops the scanner and disconnects all clients."""
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

            if self.name_filter is not None:
                if self.name_filter.lower() not in name.lower():
                    return

            client = BleakClient(device)

            if client.is_connected:
                return

            print(f"Found {name}")
            self.devices.update({device: client})

            try:
                await client.connect()
                await self.handle_connect(device, name)
            except asyncio.exceptions.CancelledError:
                print("Connection cancelled from", name)
            except BleakError:
                pass

    async def disconnect_devices(self, exclude=None):
        """Disconnects all found devices except the one defined in exclude."""
        try:
            await self.scanner.stop()
        except AttributeError:
            # self.scanner is None sometimes and checking for that in an if before
            # calling scanner.stop doesn't work on Windows for some reason
            pass

        for device, client in self.devices.items():
            if device != exclude:
                await client.disconnect()
