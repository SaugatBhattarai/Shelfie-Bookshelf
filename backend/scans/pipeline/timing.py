import time
from contextlib import contextmanager


@contextmanager
def stage(timings, name):
    """Record wall-clock ms for a pipeline stage into `timings`."""
    t0 = time.perf_counter()
    try:
        yield
    finally:
        timings[name] = round((time.perf_counter() - t0) * 1000, 1)