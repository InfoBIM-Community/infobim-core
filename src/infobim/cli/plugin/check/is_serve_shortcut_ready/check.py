from pathlib import Path
from typing import Optional

from ontobdc.storage.adapter.bootstrap import StorageBootstrap

from infobim.cli.adapter.shortcut import ServeShortcut


def main(root_path: Optional[str] = None) -> int:
    try:
        root: Path = StorageBootstrap.get_init_root_path(root_path=root_path)
        return 0 if ServeShortcut(root).is_ready() else 1
    except Exception:
        return 1
