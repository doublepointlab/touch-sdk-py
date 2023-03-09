from itertools import tee

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
