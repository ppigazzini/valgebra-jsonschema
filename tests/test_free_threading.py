"""A free-threaded interpreter keeps its GIL off once the package is imported."""

from __future__ import annotations

import subprocess
import sys
import sysconfig

import pytest

# Every module of the package, imported as a caller's program imports it. `-I` puts neither the
# working directory nor a `PYTHON*` variable on the child's path, so the child reads the
# installed package, and a `PYTHON_GIL` the caller set leaves the answer to the modules.
PROGRAM = """
import importlib, pkgutil, sys
import valgebra_jsonschema as package
for module in pkgutil.iter_modules(package.__path__):
    importlib.import_module(f"valgebra_jsonschema.{module.name}")
sys.exit(1 if sys._is_gil_enabled() else 0)
"""


@pytest.mark.skipif(
    not sysconfig.get_config_var("Py_GIL_DISABLED"),
    reason="a build with a GIL has none to keep off",
)
def test_an_import_leaves_the_gil_off() -> None:
    """Importing every module leaves a free-threaded interpreter without a GIL.

    An extension that does not declare itself free-threading-ready makes the interpreter turn
    the GIL back on at import, with a `RuntimeWarning` and no error, and the suite then passes
    on a build running as a GIL build does. The package imports one extension, valgebra's, and
    this row fails where an import turns the GIL on: the warning is an error in the child.
    """
    child = subprocess.run(  # noqa: S603 - this interpreter, a fixed program
        [sys.executable, "-I", "-W", "error", "-c", PROGRAM],
        capture_output=True,
        text=True,
        encoding="locale",
        check=False,
    )
    assert child.returncode == 0, child.stderr
