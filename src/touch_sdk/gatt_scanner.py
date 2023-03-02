import asyncio

from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError
import asyncio_atexit

__doc__ = """Scans for Bluetooth devices with a given GATT service UUID."""


class GattScanner:
    """Scans for Bluetooth devices with service_uuid.

    connection_handler gets called every time the scanner finds a new device.
    It should take parameters device and name.

    If name_filter is present, GattScanner will only find devices which contain
    that string in their name."""

    def __init__(self, on_scan_result, service_uuid, name_filter=None):
        """Creates a new instance of BLEConnector. Does not start the scanning."""
        self.on_scan_result = on_scan_result
        self.service_uuid = service_uuid
        self.name_filter = name_filter
        self.scanner = None
        self._devices = set()
        self.start_event = asyncio.Event()
        self.stop_event = asyncio.Event()

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
        asyncio_atexit.register(self.stop_scanner)
        while True:

            self.start_event.clear()
            self.stop_event.clear()
            print("start scan")

            async with BleakScanner(
                self._detection_callback, service_uuids=[self.service_uuid]
            ) as scanner:
                await self.stop_event.wait()

            print("stop scan")
            await self.start_event.wait()

    async def stop_scanner(self):
        """Stops the scanner."""
        self.stop_event.set()

    async def start_scanner(self):
        """Start the scanner. This function should not be called before GattScanner.run
        or GattScanner.start have been called."""
        self._devices.clear()  # Reset found devices list
        self.start_event.set()

    def forget_device(self, device):
        self._devices = self._devices - {device}

    async def _detection_callback(self, device, advertisement_data):
        print("scanning...")

        if device in self._devices:
            return

        self._devices.add(device)

        name = (
            advertisement_data.manufacturer_data.get(0xFFFF, bytearray()).decode(
                "utf-8"
            )
            or advertisement_data.local_name
        )

        if self.service_uuid in advertisement_data.service_uuids:

            if self.name_filter is not None:
                if self.name_filter.lower() not in name.lower():
                    return

            print(f"Found {name}")

            await self.on_scan_result(device, name)
