"""Installed CLI routing for `infobim 2d --enable`.

The ``--enable`` command runs ``pip install --upgrade infobim[2d]`` in the
active interpreter. The valid route is therefore not executed in these tests,
because it would mutate the test environment (and the development venv). The
routing — what ``TwoDEnableCommand.accepts`` and ``check`` admit — is covered
exhaustively instead.
"""

from typing import Tuple

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, InfobimCliProcessRunner


class TestInfobimTwoDEnableCommand:

    @pytest.mark.parametrize(
        "args",
        [
            ("--enable", "--help"),
            ("--enable", "extra"),
            ("--enable", "--enable"),
            ("--unknown",),
            ("--enable", "--unknown", "value"),
        ],
    )
    def test_invalid_enable_route_does_not_run_pip(
        self,
        cli_runner: InfobimCliProcessRunner,
        args: Tuple[str, ...],
    ) -> None:
        """
        Every route but the exact ``2d --enable`` must fail before reaching
        ``run()``, so ``pip install`` is never invoked.
        """
        result: CliInvocationResult = cli_runner.run("2d", *args)

        assert result.exit_code != 0, result.stdout
        assert "2D Viewer" not in result.stdout
