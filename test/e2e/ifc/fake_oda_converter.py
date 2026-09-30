"""
Test-only stand-in for the ODA File Converter.

Called with the ODA command line (input folder, output folder, version,
format, recurse, audit, file filter), it writes the DXF named by
``INFOBIM_E2E_ODA_DXF`` as the converted drawing and records the call in
``INFOBIM_E2E_ODA_LOG``.
"""

import os
import sys
import json
import shutil
from typing import List
from pathlib import Path


def main(arguments: List[str]) -> int:
    incoming: Path = Path(arguments[0])
    outgoing: Path = Path(arguments[1])
    source_name: str = arguments[6]
    converted: Path = outgoing / (Path(source_name).stem + ".dxf")
    shutil.copyfile(os.environ["INFOBIM_E2E_ODA_DXF"], converted)
    Path(os.environ["INFOBIM_E2E_ODA_LOG"]).write_text(
        json.dumps(
            {
                "input": str(incoming / source_name),
                "arguments": arguments,
                "output": str(converted),
            }
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
