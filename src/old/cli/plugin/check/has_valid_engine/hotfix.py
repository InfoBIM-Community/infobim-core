from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from infobim.shared.adapter.config import ConfigDataAdapter

_DEFAULT_ENGINE: str = "venv"


def _make_config_adapter(root_path: Optional[str] = None) -> ConfigDataAdapter:
    if isinstance(root_path, str) and root_path.strip():
        resolved_root_path: Path = Path(root_path).expanduser().resolve()
        return ConfigDataAdapter(root_dir=str(resolved_root_path))

    return ConfigDataAdapter()


def main(root_path: Optional[str] = None) -> int:
    try:
        config_adapter: ConfigDataAdapter = _make_config_adapter(root_path=root_path)
        config_file: Path = config_adapter.path
        config_file.parent.mkdir(parents=True, exist_ok=True)

        current_config: Dict[str, Any] = {}
        if config_file.is_file():
            with open(config_file, "r", encoding="utf-8") as file_handle:
                loaded_config: Any = yaml.safe_load(file_handle) or {}

            if isinstance(loaded_config, dict):
                current_config = loaded_config

        engine: object = current_config.get("engine")
        if not isinstance(engine, str) or not engine.strip():
            current_config["engine"] = _DEFAULT_ENGINE

        with open(config_file, "w", encoding="utf-8") as file_handle:
            yaml.safe_dump(current_config, file_handle, default_flow_style=False, sort_keys=False)

        return 0
    except Exception:
        return 1
