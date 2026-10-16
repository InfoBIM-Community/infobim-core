"""Qt binding is a required test dependency."""

import os
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtWidgets import QApplication
except ImportError as error:
    raise RuntimeError(
        "Install PySide6-Essentials for annotation unit tests"
    ) from error


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app
