import asyncio
import sys
import platform
from functools import partial
import logging

import bleak
from bleak import BleakClient

from touch_sdk.uuids import PROTOBUF_OUTPUT, PROTOBUF_INPUT, INTERACTION_SERVICE
from touch_sdk.gatt_scanner import GattScanner

# pylint: disable=no-name-in-module
from touch_sdk.protobuf.watch_output_pb2 import Update
from touch_sdk.protobuf.watch_input_pb2 import InputUpdate, ClientInfo


__doc__ = """Discovering Touch SDK compatible BLE devices and interfacing with them."""

logger = logging.getLogger(__name__)


class WatchConnector:
    """TODO"""

    def __init__(self, on_approved_connection, on_message, name_filter=None):
        """Creates a new instance of Watch. Does not start scanning for Bluetooth
        devices. Use Watch.start to enter the scanning and connection event loop.

        Optional name_filter connects only to watches with that name (case insensitive)"""
        self._scanner = GattScanner(
            self._on_scan_result, INTERACTION_SERVICE, name_filter
        )
        self._approved_devices = set()
        self._connected_addresses = set()
        self._informed_addresses = (
            set()
        )  # Bluetooth addresses to which client info has successfully been sent
        self._clients = {}
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

            await client.connect()
            self._clients[device.address] = client

            await self._send_client_info(client)

            await client.start_notify(
                PROTOBUF_OUTPUT, partial(self._on_protobuf, device, name)
            )

        except bleak.exc.BleakDBusError as error:
            # catching:
            # - ATT Invalid Handle error, coming from _send_client_info
            # - le-connection-abort-by-local, coming from client.connect
            logger.warning(f"{error}. Disconnecting {name}.")
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
            await self._handle_approved_connection(device, name)
            await self._on_message(message)

    async def _handle_approved_connection(self, device, name):
        if device in self._approved_devices:
            return
        self._approved_devices.add(device)

        for address in self._clients:
            if address != device.address:
                self.disconnect(device)

        if (client := self._clients.get(device.address)) is not None:
            logger.info(f"Connection approved by ${name}")
            await self._on_approved_connection(client)

    async def _handle_disconnect_signal(self, device, name):
        logger.info(f"Connection declined from {name}")
        await self.disconnect(device)

    async def _send_client_info(self, client):
        if client.address in self._informed_addresses:
            return

        client_info = ClientInfo()
        client_info.appName = sys.argv[0]
        client_info.deviceName = platform.node()
        client_info.os = platform.system()
        input_update = InputUpdate()
        input_update.clientInfo.CopyFrom(client_info)
        await client.write_gatt_char(PROTOBUF_INPUT, input_update.SerializeToString())

        self._informed_addresses.add(client.address)
