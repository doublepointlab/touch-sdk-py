__doc__ = """
GATT related UUIDs.

INTERACTION_SERVICE is needed for scanning while the Wear OS
app is backwards compatible, since the watch can only advertise
one service UUID.
"""

INTERACTION_SERVICE = "008e74d0-7bb3-4ac5-8baf-e5e372cced76"
PROTOBUF_SERVICE = "f9d60370-5325-4c64-b874-a68c7c555bad"
PROTOBUF_OUTPUT = "f9d60371-5325-4c64-b874-a68c7c555bad"
PROTOBUF_INPUT = "f9d60372-5325-4c64-b874-a68c7c555bad"
