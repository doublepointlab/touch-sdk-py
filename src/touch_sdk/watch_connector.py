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
    """Manages connections to watches.

    Handles the connection lifecycle of any number of watches, including:
    - connecting
    - getting data
    - handling connection approval
    - disconnecting (either soft or hard)

    Passes data from an approved connection to a callback (usually provided to it by a
    Watch instance).

    Discovering the Bluetooth devices is delegated to a GattScanner instance.
    """

    def __init__(self, on_approved_connection, on_message, name_filter=None):
        """Creates a new instance of WatchConnector. Does not start scanning for Bluetooth
        devices. Use WatchConnector.run to enter the scanning and connection event loop.

        Optional name_filter connects only to watches with that name (case insensitive)"""
        self._scanner = GattScanner(
            self._on_scan_result, INTERACTION_SERVICE, name_filter
        )
        self._approved_addresses = set()
        self._informed_addresses = (
            set()
        )  # Bluetooth addresses to which client info has successfully been sent
        self._tasks = set()
        self._clients = {}
        self._on_approved_connection = on_approved_connection
        self._on_message = on_message

    async def run(self):
        """Asynchronous blocking event loop that starts the Bluetooth scanner and connection loop.

        Makes it possible to run multiple async event loops with e.g. asyncio.gather."""
        await self._start_connection_monitor()
        await self._scanner.run()

    async def _start_connection_monitor(self):
        loop = asyncio.get_running_loop()
        task = loop.create_task(self._monitor_connections())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _monitor_connections(self):
        while True:
            # Make sure disconnect is called for all clients for which
            # is_connected is False (because of a physical disconnect, for example)
            disconnect_tasks = [
                self.disconnect(address)
                for address, client in self._clients.items()
                if not client.is_connected
            ]

            await asyncio.gather(*disconnect_tasks)
            await asyncio.sleep(2)

    async def _on_scan_result(self, device, name):
        try:
            client = BleakClient(device)

            await client.connect()
            self._clients[device.address] = client

            await self._send_client_info(client)

            await client.start_notify(
                PROTOBUF_OUTPUT, partial(self._on_protobuf, device, name)
            )

        except (
            bleak.exc.BleakDBusError,
            bleak.exc.BleakError,
            asyncio.TimeoutError,
        ) as error:
            # catches:
            # - ATT Invalid Handle error, coming from _send_client_info
            # - le-connection-abort-by-local, coming from client.connect
            # - Characteristic not found, coming from_send_client_info or client.start_notify
            # - asyncio timeout error, coming from client.connect
            logger.warning(f"{error}. Disconnecting {name}.")
            await self.disconnect(device.address)

    async def disconnect(self, address):
        """Disconnect the client associated with the argument device if it exists,
        and clean up.
        """
        if (client := self._clients.pop(address, None)) is not None:
            await client.disconnect()

        self._approved_addresses.discard(address)
        self._scanner.forget_address(address)

        if not self._approved_addresses:
            await self._scanner.start_scanning()

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
        if device.address in self._approved_addresses:
            return
        self._approved_addresses.add(device.address)

        if (client := self._clients.get(device.address)) is not None:
            logger.info(f"Connection approved by ${name}")
            await self._scanner.stop_scanning()

            disconnect_tasks = [
                self.disconnect(address)
                for address in self._clients
                if address != device.address
            ]

            await asyncio.gather(*disconnect_tasks)

            try:
                await self._on_approved_connection(client)
            except bleak.exc.BleakDBusError as _:
                # Catches "Unlikely GATT error"
                self.disconnect(device.address)

    async def _handle_disconnect_signal(self, device, name):
        logger.info(f"Connection declined from {name}")
        await self.disconnect(device.address)

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
