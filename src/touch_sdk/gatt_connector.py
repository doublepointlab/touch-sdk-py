from dataclasses import dataclass
from enum import Enum
import asyncio
from typing import Tuple, Optional
import sys
import platform
import struct
import re
from itertools import accumulate, chain
from functools import partial

import bleak
from bleak import BleakClient

from touch_sdk.uuids import PROTOBUF_OUTPUT, PROTOBUF_INPUT, INTERACTION_SERVICE
from touch_sdk.utils import pairwise
from touch_sdk.gatt_scanner import GattScanner

# pylint: disable=no-name-in-module
from touch_sdk.protobuf.watch_output_pb2 import Update, Gesture, TouchEvent
from touch_sdk.protobuf.watch_input_pb2 import InputUpdate, HapticEvent, ClientInfo


__doc__ = """Discovering Touch SDK compatible BLE devices and interfacing with them."""


class GattConnector:
    """TODO"""

    def __init__(self, on_approved_connection, name_filter=None):
        """Creates a new instance of Watch. Does not start scanning for Bluetooth
        devices. Use Watch.start to enter the scanning and connection event loop.

        Optional name_filter connects only to watches with that name (case insensitive)"""
        self._scanner = GattScanner(
            self._on_scan_result, INTERACTION_SERVICE, name_filter
        )
        self._connected_devices = set()
        self._approved_devices = set()
        self._on_approved_connection = on_approved_connection
        self._disconnect_events = {}

    def start(self):
        """Blocking event loop that starts the Bluetooth scanner."""
        self._scanner.start()

    async def run(self):
        """Asynchronous blocking event loop that starts the Bluetooth scanner.

        Makes it possible to run multiple async event loops with e.g. asyncio.gather."""
        await self._scanner.run()

    def stop(self):
        """Stops bluetooth scanner."""
        self._connector.stop_scanner()

    async def _on_scan_result(self, device, name):

        self._disconnect_events[device] = asyncio.Event()

        try:
            async with BleakClient(device) as client:
                self._connected_devices.add(device)
                try:
                    await client.start_notify(
                        PROTOBUF_OUTPUT, partial(self._on_protobuf, device, name)
                    )
                except ValueError:
                    pass

                await self._send_client_info(client)

                if (
                    disconnect_event := self._disconnect_events.get(device)
                ) is not None:
                    await disconnect_event.wait()
        except bleak.exc.BleakDBusError as e:
            # catching:
            # - a benign ATT Handle error here, somehow caused by _send_client_info
            # - random le-connection-abort-by-local
            print(f"connector caught {e}")

        print("removing device from connected devices")
        self._connected_devices = self._connected_devices - {device}
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

    async def _handle_approved_connection(self, device, name):
        if device in self._approved_devices:
            return
        self._approved_devices.add(device)
        await self._scanner.stop_scanner()

        print("Approved connection")
        for _, event in self._disconnect_events.items():
            event.set()

        await self._wait_for_all_disconnected()
        await self._on_approved_connection(device, name)

    async def _wait_for_all_disconnected(self):
        while self._connected_devices:
            await asyncio.sleep(0)

    async def _handle_disconnect_signal(self, device, name):
        self._disconnect_events[device].set()
        print(f"Connection declined from {name}")

    async def _send_client_info(self, client):
        client_info = ClientInfo()
        client_info.appName = sys.argv[0]
        client_info.deviceName = platform.node()
        client_info.os = platform.system()
        input_update = InputUpdate()
        input_update.clientInfo.CopyFrom(client_info)
        await client.write_gatt_char(PROTOBUF_INPUT, input_update.SerializeToString())
