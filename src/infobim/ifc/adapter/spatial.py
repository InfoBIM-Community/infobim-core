"""Spatial-container and spatial-structure lookups for IFC models.

``IfcBuildingStorey`` is the canonical host for annotations, grids,
fixtures and most user-visible BIM content; centralising its resolution
here avoids every capability re-implementing the same GlobalId /
single-default / multi-storey disambiguation dance.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class SpatialContainerRepository:
    """Resolve spatial containers (``IfcBuildingStorey``, …) from an IFC model."""

    def __init__(self, model: Any) -> None:
        self._model = model

    # ── IfcBuildingStorey ────────────────────────────────────────────────────

    def list_storeys(self) -> list[Any]:
        return list(self._model.by_type("IfcBuildingStorey"))

    def get_storey(self, storey_global_id: Optional[str] = None) -> Any:
        """Return a single ``IfcBuildingStorey``.

        * ``storey_global_id`` provided → exact GlobalId match (raise if missing).
        * Model has exactly one storey → return it.
        * Model has multiple storeys and no GlobalId → raise with a clear error.
        """
        storeys = self.list_storeys()
        if not storeys:
            raise ValueError("No IfcBuildingStorey found to host the annotation or grid.")
        if storey_global_id:
            matches = [s for s in storeys if getattr(s, "GlobalId", None) == storey_global_id]
            if not matches:
                raise ValueError(
                    f"IfcBuildingStorey with GlobalId '{storey_global_id}' was not found."
                )
            return matches[0]
        if len(storeys) > 1:
            raise ValueError(
                "The IFC contains more than one IfcBuildingStorey; pass 'storey_global_id' explicitly."
            )
        return storeys[0]

    def infer_storey_from_grid(self, grid_name: str) -> Any:
        """Used when a capability rebuilds an *existing* grid and wants to
        re-attach the new grids to the same spatial container the old grids
        lived in (e.g. multi-storey resizing without an explicit ID)."""
        grids = [g for g in self._model.by_type("IfcGrid") if getattr(g, "Name", None) == grid_name]
        if not grids:
            raise ValueError(
                f"No IfcGrid named '{grid_name}' was present; cannot infer the hosting storey."
            )
        for rel in grids[0].ContainedInStructure or ():
            return rel.RelatingStructure
        raise ValueError(
            f"IfcGrid '{grid_name}' has no ContainedInStructure relation; cannot infer the hosting storey."
        )

    # ── Hosted-element inspection (reverse) ──────────────────────────────────

    def hosted_grids_by_name(self) -> Dict[str, Any]:
        """Return a ``{Name: IfcGrid}`` map of every ``IfcGrid`` in the model."""
        return {getattr(g, "Name", None): g for g in self._model.by_type("IfcGrid") if getattr(g, "Name", None)}
