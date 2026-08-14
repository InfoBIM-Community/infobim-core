
import os
import json
from typing import Any, Optional, List, Dict
from stack.src.tui.util.path import get_project_root
from stack.src.bib.core.port.project.parameters import ProjectParametersPort


class ExternalParametersRepository(ProjectParametersPort):
    def __init__(self, base_dir: Optional[str] = None):
        root = get_project_root()
        self.base_dir = base_dir or os.path.join(root, "data", "dataset")

    def _candidate_files(self, delivery_id: Optional[str] = None) -> List[str]:
        files = []
        if delivery_id:
            files.append(os.path.join(self.base_dir, f"delivery_{delivery_id}.json"))
        else:
            delivery_dir = self.base_dir
            if os.path.isdir(delivery_dir):
                for name in sorted(os.listdir(delivery_dir), reverse=True):
                    if name.startswith("delivery_") and name.endswith(".json"):
                        files.append(os.path.join(delivery_dir, name))
        files.append(os.path.join(self.base_dir, "project.json"))
        files.append(os.path.join(self.base_dir, "asset.json"))
        files.append(os.path.join(self.base_dir, "organization.json"))
        files.append(os.path.join(self.base_dir, "standard.json"))
        return files

    def _load_json(self, path: str) -> Dict[str, Any]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f) or {}
        except Exception:
            return {}

    def _traverse(self, data: Dict[str, Any], key_path: str) -> Any:
        cur: Any = data
        for key in key_path.split("."):
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            else:
                return None
        return cur

    def get_value(self, key_path: str, delivery_id: Optional[str] = None) -> Any:
        for path in self._candidate_files(delivery_id):
            if os.path.exists(path):
                data = self._load_json(path)
                val = self._traverse(data, key_path)
                if val is not None:
                    return val
        return None

    def get_from_source(self, source: str, key_path: str, delivery_id: Optional[str] = None) -> Any:
        if source == "delivery":
            if not delivery_id:
                return None
            path = os.path.join(self.base_dir, f"delivery_{delivery_id}.json")
        else:
            path = os.path.join(self.base_dir, f"{source}.json")
        if not os.path.exists(path):
            return None
        data = self._load_json(path)
        return self._traverse(data, key_path)

    def get_merged(self, delivery_id: Optional[str] = None) -> Dict[str, Any]:
        merged: Dict[str, Any] = {}
        def deep_merge(target: Dict[str, Any], source: Dict[str, Any]) -> Dict[str, Any]:
            for k, v in source.items():
                if k in target and isinstance(target[k], dict) and isinstance(v, dict):
                    target[k] = deep_merge(target[k], v)
                else:
                    target[k] = v
            return target
        for path in reversed(self._candidate_files(delivery_id)):
            if os.path.exists(path):
                data = self._load_json(path)
                merged = deep_merge(merged, data)
        return merged
