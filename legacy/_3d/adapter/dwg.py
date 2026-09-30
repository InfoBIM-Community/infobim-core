"""Convert local DWG files to IFCX through an installed ODA File Converter."""

import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess

import ezdxf
from ezdxf.document import Drawing

from infobim.drawing.model import DrawingPlacement
from infobim.drawing.adapter.dxf import DxfConversion, DxfConverter
from infobim.drawing.adapter.oda import OdaExecutable


class DwgConverter:
    def __init__(self) -> None:
        self._executable: Path = OdaExecutable.resolve()

    def convert(self, source: Path, identifier: str, placement: DrawingPlacement) -> DxfConversion:
        temporary: str
        with TemporaryDirectory(prefix="infobim-dwg-") as temporary:
            incoming: Path = Path(temporary) / "input"
            outgoing: Path = Path(temporary) / "output"
            incoming.mkdir()
            outgoing.mkdir()
            shutil.copyfile(source, incoming / "drawing.dwg")
            result: subprocess.CompletedProcess[str] = subprocess.run(
                [str(self._executable), str(incoming), str(outgoing), "ACAD2018", "DXF", "0", "0", "drawing.dwg"],
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            converted: Path = outgoing / "drawing.dxf"
            if result.returncode != 0 or not converted.is_file():
                raise RuntimeError(
                    f"DWG conversion failed for {source.name} (exit {result.returncode}). "
                    f"stdout: {result.stdout.strip()}; stderr: {result.stderr.strip()}"
                )
            drawing: Drawing = ezdxf.readfile(converted)
            return DxfConverter.from_drawing(drawing, source.name, identifier, placement)
