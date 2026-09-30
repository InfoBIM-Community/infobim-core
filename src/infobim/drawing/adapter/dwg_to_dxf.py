"""Convert a local DWG file into a cached, content-addressed DXF payload."""

import shutil
from typing import ClassVar
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess

from infobim.drawing.adapter.oda import OdaExecutable
from infobim.drawing.adapter.transformation_payload import TransformationPayloadPath


class DwgToDxfConverter:
    """Independent DWG -> DXF transformation, cached by source content.

    Does not parse or interpret the DXF it produces; that belongs to the
    DXF -> IFCX transformation. This one only owns getting a DWG through
    the ODA File Converter and persisting the result.
    """

    SOURCE_FORMAT: ClassVar[str] = "dwg"
    TARGET_FORMAT: ClassVar[str] = "dxf"
    ODA_TARGET_VERSION: ClassVar[str] = "ACAD2018"
    INPUT_NAME: ClassVar[str] = "drawing.dwg"
    OUTPUT_NAME: ClassVar[str] = "drawing.dxf"

    def convert(self, container: Path, source: Path) -> Path:
        if source.suffix.lower() != ".dwg":
            raise ValueError(f"Not a DWG file: {source}")
        if not source.is_file():
            raise ValueError(f"Source DWG file is missing: {source}")

        identifier: str = TransformationPayloadPath.identifier_for(source)
        destination: Path = TransformationPayloadPath.resolve(
            container, self.SOURCE_FORMAT, self.TARGET_FORMAT, identifier, ".dxf",
        )
        if destination.is_file():
            return destination

        executable: Path = OdaExecutable.resolve()
        temporary: str
        with TemporaryDirectory(prefix="infobim-drawing-dwg-") as temporary:
            incoming: Path = Path(temporary) / "input"
            outgoing: Path = Path(temporary) / "output"
            incoming.mkdir()
            outgoing.mkdir()
            shutil.copyfile(source, incoming / self.INPUT_NAME)
            result: subprocess.CompletedProcess[str] = subprocess.run(
                [
                    str(executable), str(incoming), str(outgoing),
                    self.ODA_TARGET_VERSION, "DXF", "0", "0", self.INPUT_NAME,
                ],
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            converted: Path = outgoing / self.OUTPUT_NAME
            if result.returncode != 0 or not converted.is_file():
                raise RuntimeError(
                    f"DWG conversion failed for {source.name} (exit {result.returncode}). "
                    f"stdout: {result.stdout.strip()}; stderr: {result.stderr.strip()}"
                )
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(converted, destination)

        return destination
