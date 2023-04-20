import asyncio

from bleak import BleakScanner

__doc__ = """Scans for Bluetooth devices with a given GATT service UUID."""

class GattScanner:
    """Scans for Bluetooth devices with service_uuid.

    on_scan_result gets called every time the scanner finds a new device.
    It should take parameters device and name.

    If name_filter is present, GattScanner will only find devices which contain
    that string in their name."""

    def __init__(self, on_scan_result, service_uuid, name_filter=None):
        """Creates a new instance of GattScanner. Does not start the scanning."""
        self.on_scan_result = on_scan_result
        self.service_uuid = service_uuid
        self.name_filter = name_filter
        self.scanner = None
        self._addresses = set()
        self._scanning = False

    async def start(self):
        """Start the scanner."""

        scanner = BleakScanner(
            self._detection_callback, service_uuids=[self.service_uuid]
        )

        await self.start_scanning()
        await scanner.start()

    async def stop_scanning(self):
        """Stop scanning."""
        self._scanning = False

    async def start_scanning(self):
        """Start scanning. This function should not be called before GattScanner.run
        has been called."""
        if not self._scanning:
            self._addresses.clear()  # Reset found addresses list
        self._scanning = True
        print("Scanning...")

    def forget_address(self, address):
        """Forget address, i.e., act as if the device with that address had
        never been discovered."""
        self._addresses.discard(address)

    async def _detection_callback(self, device, advertisement_data):
        if not self._scanning:
            return

        if device.address in self._addresses:
            return
        self._addresses.add(device.address)

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
