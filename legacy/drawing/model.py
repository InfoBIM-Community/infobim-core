"""Contracts for local drawing placement and offline IFCX documents."""

from math import isfinite
from typing import Any, ClassVar, Dict, List, Optional, Tuple
from dataclasses import dataclass


Matrix = Tuple[Tuple[float, float, float, float], ...]


@dataclass(frozen=True)
class DrawingPlacement:
    """USD row-vector transform in metres; absent placement means identity."""

    IDENTITY: ClassVar[Matrix] = (
        (1.0, 0.0, 0.0, 0.0),
        (0.0, 1.0, 0.0, 0.0),
        (0.0, 0.0, 1.0, 0.0),
        (0.0, 0.0, 0.0, 1.0),
    )
    transform: Matrix = IDENTITY
    meters_per_unit: Optional[float] = None

    def __post_init__(self) -> None:
        if len(self.transform) != 4 or any(len(row) != 4 for row in self.transform):
            raise ValueError("Drawing transform must be a 4 x 4 matrix.")
        value: float
        for row in self.transform:
            for value in row:
                self._finite_number(value, "Drawing transform")
        if tuple(row[3] for row in self.transform) != (0.0, 0.0, 0.0, 1.0):
            raise ValueError("Drawing transform must be affine with translation in its last row.")
        if self.meters_per_unit is not None:
            self._finite_number(self.meters_per_unit, "meters_per_unit")
            if self.meters_per_unit <= 0:
                raise ValueError("meters_per_unit must be positive.")

    @staticmethod
    def _finite_number(value: Any, label: str) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
            raise ValueError(f"{label} must contain finite numbers.")

    @classmethod
    def from_json(cls, value: Any) -> "DrawingPlacement":
        if not isinstance(value, dict) or set(value) - {"transform", "meters_per_unit"}:
            raise ValueError("Drawing settings accept only transform and meters_per_unit.")
        transform: Matrix = cls.IDENTITY
        if "transform" in value:
            rows: Any = value["transform"]
            if not isinstance(rows, list) or not all(isinstance(row, list) for row in rows):
                raise ValueError("Drawing transform must be an array of four rows.")
            transform = tuple(tuple(row) for row in rows)
        scale: Optional[float] = None
        if "meters_per_unit" in value:
            scale = value["meters_per_unit"]
            if scale is None:
                raise ValueError("An explicit meters_per_unit cannot be null.")
        return cls(transform=transform, meters_per_unit=scale)

    def with_unit_scale(self, scale: float) -> List[List[float]]:
        self._finite_number(scale, "Drawing unit scale")
        if scale <= 0:
            raise ValueError("Drawing unit scale must be positive.")
        return [
            [value * scale if index < 3 else value for value in row]
            for index, row in enumerate(self.transform)
        ]


class IfcxDocument:
    USD_URI: ClassVar[str] = "https://ifcx.dev/@openusd.org/usd@v1.ifcx"

    @classmethod
    def create(cls, identifier: str, nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "header": {
                "id": identifier,
                "ifcxVersion": "ifcx_alpha",
                "dataVersion": "1.0.0",
                "author": "InfoBIM",
            },
            "imports": [{"uri": cls.USD_URI}],
            "schemas": {
                "infobim::name": {"value": {"dataType": "String"}},
                "infobim::globalId": {"value": {"dataType": "String"}},
            },
            "data": nodes,
        }

    @staticmethod
    def validate(value: Any, source: str) -> Dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError(f"IFCX document must be an object: {source}")
        header: Any = value.get("header")
        if not isinstance(header, dict):
            raise ValueError(f"IFCX document has no header: {source}")
        identifier: Any = header.get("id")
        if not isinstance(identifier, str) or not identifier.strip():
            raise ValueError(f"IFCX document has no layer ID: {source}")
        if not isinstance(value.get("imports"), list) or not isinstance(value.get("data"), list):
            raise ValueError(f"IFCX imports and data must be arrays: {source}")
        if not isinstance(value.get("schemas"), dict):
            raise ValueError(f"IFCX schemas must be an object: {source}")
        return value
