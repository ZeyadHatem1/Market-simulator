from pathlib import Path

from pybind11.setup_helpers import Pybind11Extension, build_ext
from setuptools import setup

# Only ext_modules needs a setup.py at all -- everything else (name, version,
# deps, package discovery) is declared in pyproject.toml. See
# docs/decisions/ADR-005-native-matching-engine-boundary.md for why this is
# setuptools + pybind11.Extension rather than CMake/scikit-build-core.
NATIVE_SRC = Path("src/market_sim/exchange/native/cpp")

ext_modules = [
    Pybind11Extension(
        "market_sim.exchange.native._core",
        sources=[
            str(NATIVE_SRC / "bindings.cpp"),
            str(NATIVE_SRC / "order_book.cpp"),
            str(NATIVE_SRC / "matching_engine.cpp"),
        ],
        include_dirs=[str(NATIVE_SRC)],
        cxx_std=17,
    ),
]

setup(ext_modules=ext_modules, cmdclass={"build_ext": build_ext}, zip_safe=False)
