from pathlib import Path
from typing import Iterator

import pytest

from test.e2e.cli_process_runner import InfobimCliProcessRunner


@pytest.fixture
def cli_runner(tmp_path: Path) -> Iterator[InfobimCliProcessRunner]:
    yield InfobimCliProcessRunner(isolated_project_root=tmp_path)
