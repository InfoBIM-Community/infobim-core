from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple


@dataclass(frozen=True)
class IfcClassPresentation:
    class_uri: str
    class_name: str
    element_count: int
    dataset_count: int
    datasets: Tuple[str, ...]
    elements: Tuple[Dict[str, Any], ...]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "class_uri": self.class_uri,
            "class_name": self.class_name,
            "element_count": self.element_count,
            "dataset_count": self.dataset_count,
            "datasets": list(self.datasets),
            "elements": [dict(element) for element in self.elements],
        }


@dataclass(frozen=True)
class InfoBIMProjectPresentation:
    project_id: str
    project_path: str
    project_subject: str
    project: Dict[str, Any]
    classes: Tuple[IfcClassPresentation, ...]

    @property
    def element_count(self) -> int:
        return sum(item.element_count for item in self.classes)

    def model_payload(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "class_count": len(self.classes),
            "element_count": self.element_count,
            "classes": [item.as_dict() for item in self.classes],
        }
