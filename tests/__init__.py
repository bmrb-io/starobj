# simple timings
#
from contextlib import contextmanager
import time
import sys

@contextmanager
def timer( label, silent = False ) :
    start = time.time()
    try :
        yield
    finally :
        end = time.time()
        if not silent :
            sys.stdout.write( "%s: %0.3f\n" % (label,(end - start)) )

from .passthru import passthru

__all__ = [ "timer",
    "passthru" ]

#
