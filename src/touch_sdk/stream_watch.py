import base64
from platform import platform
import select
import binascii
import sys
import asyncio
import asyncio_atexit

from touch_sdk.uuids import PROTOBUF_OUTPUT, PROTOBUF_INPUT
from touch_sdk.watch_connector import WatchConnector

from touch_sdk.protobuf.watch_output_pb2 import Update  # type: ignore
import logging

logger = logging.getLogger(__file__)


__doc__ = """Protobuffers streamed in base64 through stdin/stdout"""


class StreamWatch:
    """Scans Touch SDK compatible Bluetooth LE devices and connects to the first one
    of them that approves the connection.

    Watch also parses the data that comes over Bluetooth and returns it through
    callback methods."""

    def __init__(self, name_filter=None):
        """Creates a new instance of StreamWatch. Does not start scanning for Bluetooth
        devices. Use Watch.start to enter the scanning and connection event loop.

        Optional name_filter connects only to watches with that name (case insensitive)
        """
        self._connector = WatchConnector(
            self._on_approved_connection, self._on_protobuf, name_filter
        )

        self._client = None
        self._stop_event = None
        self._event_loop = None

    def start(self):
        """Blocking event loop that starts the Bluetooth scanner

        More handy than Watch.run when only this event loop is needed."""
        try:
            asyncio.run(self.run())
        except KeyboardInterrupt:
            pass

    def stop(self):
        """Stop the watch, disconnecting any connected devices."""
        if self._stop_event is not None:
            self._stop_event.set()

    async def run(self):
        """Asynchronous blocking event loop that starts the Bluetooth scanner.

        Makes it possible to run multiple async event loops with e.g. asyncio.gather."""

        self._event_loop = asyncio.get_running_loop()
        self._stop_event = asyncio.Event()

        asyncio_atexit.register(self.stop)

        await self._connector.start()
        await self._input_loop()
        await self._stop_event.wait()
        await self._connector.stop()

    @staticmethod
    def tinput() -> str:
        rfds, _, _ = select.select([sys.stdin], [], [], 1)
        if rfds:
            logger.debug("input!")
            return rfds[0].readline()
        else:
            logger.debug("no input")
            return ""

    @staticmethod
    async def ainput() -> str:
        if platform() == "Windows":
            return await asyncio.to_thread(sys.stdin.readline)
        else:
            return await asyncio.to_thread(StreamWatch.tinput)

    async def _input_loop(self):
        while self._stop_event is not None and not self._stop_event.is_set():
            str = await StreamWatch.ainput()
            str = str.strip()
            if str:
                self._input(str)

    def _on_protobuf(self, pf: Update):
        """Bit simpler to let connector parse and serialize protobuf again
        than to override connector behaviour.
        """
        logger.debug("_on_protobuf")
        self._output(pf.SerializeToString())

    def _input(self, base64data):
        """Write protobuf data to input characteristic"""
        try:
            self._write_input_characteristic(base64.b64decode(base64data), self._client)
        except binascii.Error as e:
            logger.error("Decode err: %s", e)

    def _output(self, data):
        print(base64.b64encode(data))

    async def _on_approved_connection(self, client):
        logger.debug("_on_approved_connection")
        self._client = client
        await self._fetch_info(client)

    async def _fetch_info(self, client):
        data = await client.read_gatt_char(PROTOBUF_OUTPUT)
        self._output(data)

    def _write_input_characteristic(self, data, client):
        if self._event_loop is not None:
            self._event_loop.create_task(
                self._async_write_input_characteristic(PROTOBUF_INPUT, data, client)
            )

    async def _async_write_input_characteristic(self, characteristic, data, client):
        if client:
            await client.write_gatt_char(characteristic, data, True)


def main():
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument("--name-filter", type=str, default=None)
    parser.add_argument("--debug-level", type=int, default=logging.CRITICAL + 1)
    args = parser.parse_args()
    logging.basicConfig(level=args.debug_level)

    try:
        StreamWatch(args.name_filter).start()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
