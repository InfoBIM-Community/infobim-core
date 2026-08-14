from pathlib import Path
from typing import Any, Dict, Optional

from infobim.shared.adapter.config import ConfigDataAdapter


def _make_config_adapter(root_path: Optional[str] = None) -> ConfigDataAdapter:
    if isinstance(root_path, str) and root_path.strip():
        resolved_root_path: Path = Path(root_path).expanduser().resolve()
        return ConfigDataAdapter(root_dir=str(resolved_root_path))

    return ConfigDataAdapter()


def main(root_path: Optional[str] = None) -> int:
    try:
        config_adapter: ConfigDataAdapter = _make_config_adapter(root_path=root_path)
        if not config_adapter.path.is_file():
            return 1

        config_data: Optional[Dict[str, Any]] = config_adapter.all
        if not isinstance(config_data, dict):
            return 1

        engine: object = config_data.get("engine")
        if not isinstance(engine, str) or not engine.strip():
            return 1

        return 0
    except Exception:
        return 1
