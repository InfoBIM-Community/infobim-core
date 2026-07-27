import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from ontobdc.shared.adapter.config import ConfigDataAdapter as OntoBDCConfigDataAdapter


class ConfigDataAdapter(OntoBDCConfigDataAdapter):
    """
    Adapter for retrieving and managing configuration data for the InfoBIM CLI.
    It reads settings from the `.__ontobdc__/config.yaml` and
    `.__ontobdc__/__infobim__/config.yaml` files.
    """

    def __init__(self, root_dir: str = None):
        super().__init__(root_dir=root_dir)
        ontobdc_directory: str = str(self.path.parent)
        self._infobim_config_dir: str = os.path.join(ontobdc_directory, "__infobim__")
        self._infobim_config_file: str = os.path.join(self._infobim_config_dir, "config.yaml")
        self._infobim_config_data: Dict[str, Any] = self._get_infobim_config_data()

    @property
    def infobim_config_dir(self) -> Path:
        return Path(self._infobim_config_dir)

    @property
    def infobim_config_file(self) -> Path:
        return Path(self._infobim_config_file)

    @property
    def infobim_config(self) -> Optional[Dict[str, Any]]:
        if not self._infobim_config_data:
            self._infobim_config_data = self._get_infobim_config_data()

        return self._infobim_config_data

    def _get_infobim_config_data(self) -> Dict[str, Any]:
        if not os.path.isfile(self._infobim_config_file):
            return {}

        with open(self._infobim_config_file, "r", encoding="utf-8") as file_handle:
            loaded_data: Any = yaml.safe_load(file_handle) or {}

        if isinstance(loaded_data, dict):
            return loaded_data

        return {}

    def _get_script_dir(self) -> str:
        try:
            import infobim

            if hasattr(infobim, "__path__"):
                package_path: str = str(infobim.__path__[0])
                if package_path:
                    return package_path
        except Exception:
            pass

        script_dir: str = os.path.dirname(os.path.abspath(__file__))
        module_root: str = os.path.abspath(os.path.join(script_dir, ".."))
        return module_root
