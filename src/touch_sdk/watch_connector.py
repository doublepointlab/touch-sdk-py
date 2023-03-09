import asyncio
import sys
import platform
from functools import partial

import bleak
from bleak import BleakClient

from touch_sdk.uuids import PROTOBUF_OUTPUT, PROTOBUF_INPUT, INTERACTION_SERVICE
from touch_sdk.gatt_scanner import GattScanner

# pylint: disable=no-name-in-module
from touch_sdk.protobuf.watch_output_pb2 import Update
from touch_sdk.protobuf.watch_input_pb2 import InputUpdate, ClientInfo


__doc__ = """Discovering Touch SDK compatible BLE devices and interfacing with them."""


class WatchConnector:
    """TODO"""

    def __init__(self, on_approved_connection, on_message, name_filter=None):
        """Creates a new instance of Watch. Does not start scanning for Bluetooth
        devices. Use Watch.start to enter the scanning and connection event loop.

        Optional name_filter connects only to watches with that name (case insensitive)"""
        self._scanner = GattScanner(
            self._on_scan_result, INTERACTION_SERVICE, name_filter
        )
        self._connected_addresses = set()
        self._clients = {}
        self._approved_devices = set()
        self._on_approved_connection = on_approved_connection
        self._on_message = on_message

    def start(self):
        """Blocking event loop that starts the Bluetooth scanner."""
        self._scanner.start()

    async def run(self):
        """Asynchronous blocking event loop that starts the Bluetooth scanner.

        Makes it possible to run multiple async event loops with e.g. asyncio.gather."""
        await self._scanner.run()

    def stop(self):
        """TODO"""
        return

    async def _on_scan_result(self, device, name):

        try:
            client = BleakClient(device)
            print("client init")

            await client.connect()
            self._clients[device.address] = client
            print("client connected")
            await self._send_client_info(client)
            print("client info sent")

            await client.start_notify(
                PROTOBUF_OUTPUT, partial(self._on_protobuf, device, name)
            )
            print("client subscribed")

        except bleak.exc.BleakDBusError as error:
            # catching:
            # - a benign ATT Handle error here, somehow caused by _send_client_info
            # - random le-connection-abort-by-local
            print(f"connector caught {error}")
            await self.disconnect(device)

    async def disconnect(self, device):
        """Disconnect the client associated with the argument device if it exists,
        and clean up.
        """
        if (client := self._clients.pop(device.address, None)) is not None:
            await client.disconnect()

        self._approved_devices.discard(device)
        self._scanner.forget_device(device)

    async def _on_protobuf(self, device, name, _, data):
        message = Update()
        message.ParseFromString(bytes(data))

        # Watch sent a disconnect signal. Might be because the user pressed "no"
        # from the connection dialog on the watch (was not connected to begin with),
        # or because the watch app is exiting / user pressed "forget devices"
        if any(s == Update.Signal.DISCONNECT for s in message.signals):
            await self._handle_disconnect_signal(device, name)

        # Watch sent some other data, but no disconnect signal = watch accepted
        # the connection
        else:
            await self._handle_approved_connection(device)
            await self._on_message(message)

    async def _handle_approved_connection(self, device):
        if device in self._approved_devices:
            return
        self._approved_devices.add(device)

        for address in self._clients:
            if address != device.address:
                self.disconnect(device)

        if (client := self._clients.get(device.address)) is not None:
            print("Approved connection")
            await self._on_approved_connection(client)

    async def _wait_for_all_disconnected(self):
        while self._connected_addresses:
            await asyncio.sleep(0)

    async def _handle_disconnect_signal(self, device, name):
        print(f"Connection declined from {name}")
        await self.disconnect(device)

    async def _send_client_info(self, client):
        client_info = ClientInfo()
        client_info.appName = sys.argv[0]
        client_info.deviceName = platform.node()
        client_info.os = platform.system()
        input_update = InputUpdate()
        input_update.clientInfo.CopyFrom(client_info)
        await client.write_gatt_char(PROTOBUF_INPUT, input_update.SerializeToString())
