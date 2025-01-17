import base64
from functools import partial
import binascii
import sys
import asyncio
import asyncio_atexit
from time import sleep

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

    def __init__(self, name_filter=None, disable_input=False):
        """Creates a new instance of StreamWatch. Does not start scanning for Bluetooth
        devices. Use Watch.start to enter the scanning and connection event loop.

        Optional name_filter connects only to watches with that name (case insensitive).
        If disable_input is true, watch listens to no inputs.
        """
        self._connector = WatchConnector(
            self._on_approved_connection, self._on_protobuf, name_filter
        )

        self._client = None
        self._stop_event = None
        self._event_loop = None
        self._disable_input = disable_input

    def start(self):
        """Blocking event loop that starts the Bluetooth scanner

        More handy than Watch.run when only this event loop is needed."""
        try:
            asyncio.run(self.run())
        except KeyboardInterrupt:
            logger.debug("interrupted")
            pass

    def stop(self):
        """Stop the watch, disconnecting any connected devices."""
        logger.debug("stop")
        if self._stop_event is not None:
            self._stop_event.set()

    async def run(self):
        """Asynchronous blocking event loop that starts the Bluetooth scanner.

        Makes it possible to run multiple async event loops with e.g. asyncio.gather."""

        self._event_loop = asyncio.get_running_loop()
        self._stop_event = asyncio.Event()

        asyncio_atexit.register(self.stop)

        await self._connector.start()
        if not self._disable_input:
            task1 = asyncio.create_task(self._input_loop())  # Wrap coroutines in tasks
            task2 = asyncio.create_task(self._wait_and_stop())
            _, pending = await asyncio.wait(
                [task2, task1],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for p in pending:
                p.cancel()
        else:
            await self._wait_and_stop()

    async def _wait_and_stop(self):
        assert self._stop_event
        await self._stop_event.wait()
        await self._connector.stop()

    async def _input_loop(self):
        loop = asyncio.get_running_loop()
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)

        # Connect the standard input to the StreamReader protocol
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)

        # Read lines from stdin asynchronously
        while self._stop_event is not None and not self._stop_event.is_set():
            line = await reader.readline()
            line = line.strip()
            if line:
                self._input(line)

    def _input(self, base64data):
        """Write protobuf data to input characteristic"""
        try:
            self._write_input_characteristic(base64.b64decode(base64data), self._client)
        except binascii.Error as e:
            logger.error("Decode err: %s", e)

    @staticmethod
    def _print_data(data):
        sys.stdout.buffer.write(data)
        sys.stdout.flush()

    async def _output(self, data):
        if self._stop_event and not self._stop_event.is_set():
            data = base64.b64encode(data) + b"\n"
            await asyncio.to_thread(partial(StreamWatch._print_data, data))

    async def _on_protobuf(self, pf: Update):
        """Bit simpler to let connector parse and serialize protobuf again
        than to override connector behaviour.
        """
        logger.debug("_on_protobuf")
        await self._output(pf.SerializeToString())

    async def _on_approved_connection(self, client):
        logger.debug("_on_approved_connection")
        self._client = client
        await self._fetch_info(client)

    async def _fetch_info(self, client):
        data = await client.read_gatt_char(PROTOBUF_OUTPUT)
        await self._output(data)

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
    import signal

    def rs(*_):
        raise KeyboardInterrupt()

    signal.signal(signal.SIGTERM, rs)

    parser = ArgumentParser()
    parser.add_argument("--name-filter", type=str, default=None)
    parser.add_argument("--debug-level", type=int, default=logging.CRITICAL + 1)
    parser.add_argument("--disable-input", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=args.debug_level)

    try:
        StreamWatch(args.name_filter, args.disable_input).start()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        # This is so user can see error in executable created with pynsist
        print(f"Error: {e}", file=sys.stderr)
        sleep(2)
        raise e


if __name__ == "__main__":
    main()
