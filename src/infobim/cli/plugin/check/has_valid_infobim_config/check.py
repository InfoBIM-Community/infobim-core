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
        if not config_adapter.infobim_config_dir.is_dir():
            return 1

        if not config_adapter.infobim_config_file.is_file():
            return 1

        config_data: Optional[Dict[str, Any]] = config_adapter.infobim_config
        if not isinstance(config_data, dict):
            return 1

        ifc_config: object = config_data.get("ifc")
        if not isinstance(ifc_config, dict):
            return 1

        prefered_schema: object = ifc_config.get("preferedSchema")
        if not isinstance(prefered_schema, str) or not prefered_schema.strip():
            return 1

        return 0
    except Exception:
        return 1
