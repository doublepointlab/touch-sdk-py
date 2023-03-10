import re
import struct
from itertools import accumulate, chain, tee

__doc__ = """Miscellaneous utilities."""


def pairwise(iterable):
    """Return successive overlapping pairs taken from the input iterable.

    Rougly equivalent to `itertools.pairwise` in Python >=3.10; implemented here
    for Python >=3.8 compatibility.
    """
    # pairwise('ABCDEFG') --> AB BC CD DE EF FG
    first, second = tee(iterable)
    next(second, None)
    return zip(first, second)


def unpack_chained(format_string, data):
    """
    Unpack struct data with a format string that may contain multiple
    endianness tokens.

    For example, when unpacking 8 bytes of data with the
    format string ">f<i", the first 4 bytes will be interpreted as a big-endian
    single-precision float, and the last 4 bytes will be interpreted as
    a little-endian 32-bit signed integer.
    """

    endianness_tokens = "@<>=!"

    format_description = (
        format_string if format_string[0] in endianness_tokens else "@" + format_string
    )

    format_strings = re.split(f"(?=[{endianness_tokens}])", format_description)

    sizes = [struct.calcsize(fmt) for fmt in format_strings]
    ranges = pairwise(accumulate(sizes))
    data_pieces = [data[start:end] for start, end in ranges]

    nested_content = [
        struct.unpack(fmt, piece) for piece, fmt in zip(data_pieces, format_strings[1:])
    ]
    return tuple(chain(*nested_content))
