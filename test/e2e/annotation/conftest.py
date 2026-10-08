"""Qt is mandatory; a missing binding is a collection error, not a skip."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    import PySide6
except ImportError as error:
    raise RuntimeError(
        "Install PySide6-Essentials to collect annotation e2e tests"
    ) from error
