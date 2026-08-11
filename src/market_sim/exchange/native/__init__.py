try:
    from . import _core  # noqa: F401

    NATIVE_AVAILABLE = True
except ImportError:
    NATIVE_AVAILABLE = False

from .adapter import NativeMatchingEngine, NativeOrderBook
from .gateway import build_native_exchange

__all__ = [
    "NATIVE_AVAILABLE",
    "NativeOrderBook",
    "NativeMatchingEngine",
    "build_native_exchange",
]
