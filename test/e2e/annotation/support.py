"""Subprocess runner with a Qt human driver and ordinary installed CLI setup."""

import os
import subprocess
import sys
from pathlib import Path
import ezdxf
from test.e2e.cli_process_runner import CliInvocationResult, InfobimCliProcessRunner


def project(tmp_path):
    runner = InfobimCliProcessRunner(tmp_path)
    for args in [("init",), ("project", "--create", "Hospital Norte")]:
        result = runner.run(*args)
        assert result.exit_code == 0, result.stdout + result.stderr
    drawings = [
        path
        for path in tmp_path.iterdir()
        if path.is_dir()
        and path.name != ".__ontobdc__"
        and not path.name.startswith(".")
    ]
    assert len(drawings) == 1, drawings
    directory = drawings[0]
    drawing = directory / "planta.dxf"
    doc = ezdxf.new()
    doc.modelspace().add_line((0, 0), (10, 10))
    doc.saveas(drawing)
    return directory, drawing


def run(directory, *args, mode="accept", catalog=None):
    env = os.environ.copy()
    for key in ["ONTOBDC_PROJECT_ROOT", "INFOBIM_PROJECT_ROOT"]:
        env.pop(key, None)
    root = Path(__file__).resolve().parents[3]
    ontobdc = root.parent / "ontobdc"
    env["PYTHONPATH"] = os.pathsep.join(
        [str(root / "src"), str(root), str(ontobdc / "src"), env.get("PYTHONPATH", "")]
    )
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["ANNOTATION_TEST_MODE"] = mode
    if catalog:
        env["ANNOTATION_TEST_CATALOG"] = str(catalog)
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).with_name("qt_driver.py")),
            "--json",
            *args,
        ],
        cwd=directory,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return CliInvocationResult(
        tuple(args), result.returncode, result.stdout, result.stderr
    )
