"""Extract and mutate extrusion profiles of existing parametric IFC elements.

Any parametric occurrence that uses a SweptSolid body (``IfcColumn``,
``IfcBeam``, ``IfcMember``, ``IfcPlate``, custom ``IfcBuildingElementProxy``
runs, …) stores its cross-section as the ``SweptArea`` attribute on one or
more ``IfcExtrudedAreaSolid`` items in the element's ``Body`` representation.
Changing just the ``SweptArea`` (and nothing else about the placement or
extrusion depth) is the schema-correct way to resize a column section
*without* re-computing structural attachments or re-creating owner-history
linkages a second time.

This adapter exposes two public surfaces:

* :class:`ProfileSpec` (dataclass DTO) -- a caller-facing specification of a
  desired parametric profile (4 types: RECTANGLE / RECTANGLE_HOLLOW /
  CIRCLE / CIRCLE_HOLLOW).  ``ProfileSpec`` validates its own required
  dimensions on construction so a caller that passes inconsistent inputs
  (e.g. a CIRCLE with ``width`` instead of ``outer_diameter``) fails early
  with a clear error, not a cryptic IFC-schema failure.
* :class:`IfcProfileMutator` -- bound to a single ``ifcopenshell`` model;
  knows how to (a) inspect an element occurrence and return a plain dict of
  its *current* profile info (``get_current_profile_info``), and (b) apply
  a :class:`ProfileSpec` to that same occurrence by replacing the
  ``SweptArea`` attribute on every ``IfcExtrudedAreaSolid`` found in the
  element's ``Body`` representation with a freshly-instantiated profile of
  the requested shape, **preserving** the ``Position``, ``Depth`` and
  ``ExtrudedDirection`` of each existing solid.  Representations other than
  ``Body`` (``Axis``, ``Box``, ``FootPrint`` etc.) are intentionally left
  alone -- callers should only mutate the 3D swept section.

Optional ``entities_created`` counters are updated when passed in, following
the same convention used by :class:`infobim.ifc.adapter.geometry_builder.IfcCurveBuilder`
and friends so capability reports stay uniform.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


# ProfileSpec public enum / tags.  Using plain strings so capability JSON
# schemas can accept the values directly without a second mapping layer.
PROFILE_TYPE_RECTANGLE = "RECTANGLE"
PROFILE_TYPE_RECTANGLE_HOLLOW = "RECTANGLE_HOLLOW"
PROFILE_TYPE_CIRCLE = "CIRCLE"
PROFILE_TYPE_CIRCLE_HOLLOW = "CIRCLE_HOLLOW"

VALID_PROFILE_TYPES = frozenset(
    {
        PROFILE_TYPE_RECTANGLE,
        PROFILE_TYPE_RECTANGLE_HOLLOW,
        PROFILE_TYPE_CIRCLE,
        PROFILE_TYPE_CIRCLE_HOLLOW,
    }
)


@dataclass(frozen=True)
class ProfileSpec:
    """A validated caller-facing specification of a desired parametric section.

    Only the dimensions required by ``profile_type`` are read; the others are
    expected to be ``None`` (or zero).  Using a frozen dataclass keeps the
    DTO immutable across the call stack so capabilities cannot silently
    mutate their inputs.
    """

    profile_type: str
    width: Optional[float] = None
    depth: Optional[float] = None
    outer_diameter: Optional[float] = None
    inner_diameter: Optional[float] = None
    wall_thickness: Optional[float] = None

    def __post_init__(self) -> None:
        if str(self.profile_type) not in VALID_PROFILE_TYPES:
            raise ValueError(
                f"Unknown profile_type '{self.profile_type}'. "
                f"Valid values: {sorted(VALID_PROFILE_TYPES)}."
            )
        if self.profile_type in {PROFILE_TYPE_RECTANGLE, PROFILE_TYPE_RECTANGLE_HOLLOW}:
            if self.width is None or self.depth is None:
                raise ValueError(
                    f"Profile '{self.profile_type}' requires 'width' and 'depth'."
                )
            if float(self.width) <= 0 or float(self.depth) <= 0:
                raise ValueError(
                    "Profile width and depth must be strictly greater than zero."
                )
            if self.profile_type == PROFILE_TYPE_RECTANGLE_HOLLOW:
                self._validate_hollow_wall_thickness(
                    self._rect_outer_minor()
                )
            return
        if self.outer_diameter is None:
            raise ValueError(
                f"Profile '{self.profile_type}' requires 'outer_diameter'."
            )
        if float(self.outer_diameter) <= 0:
            raise ValueError("'outer_diameter' must be strictly greater than zero.")
        if self.profile_type == PROFILE_TYPE_CIRCLE_HOLLOW:
            if self.inner_diameter is None and self.wall_thickness is None:
                raise ValueError(
                    f"Profile '{self.profile_type}' requires either 'inner_diameter' "
                    f"or 'wall_thickness'."
                )
            derived_inner = (
                float(self.inner_diameter)
                if self.inner_diameter is not None
                else float(self.outer_diameter) - 2.0 * float(self.wall_thickness or 0.0)
            )
            if derived_inner <= 0 or derived_inner >= float(self.outer_diameter):
                raise ValueError(
                    f"Invalid hollow circle section: outer_diameter="
                    f"{self.outer_diameter}, inner resolved to {derived_inner}. "
                    f"Inner must be strictly positive and strictly smaller."
                )

    def _rect_outer_minor(self) -> float:
        return min(float(self.width or 0.0), float(self.depth or 0.0))

    def _validate_hollow_wall_thickness(self, outer_minor: float) -> None:
        if self.wall_thickness is None:
            raise ValueError(
                f"Profile '{self.profile_type}' requires 'wall_thickness'."
            )
        wall = float(self.wall_thickness or 0.0)
        if wall <= 0 or 2.0 * wall >= outer_minor:
            raise ValueError(
                f"Invalid hollow rectangular section: width={self.width}, "
                f"depth={self.depth}, wall_thickness={wall}. "
                f"Wall must be positive and strictly less than half of the smaller dimension."
            )


# ── Mutator implementation ──────────────────────────────────────────────────

class IfcProfileMutator:
    """Replace the ``SweptArea`` on every ``IfcExtrudedAreaSolid`` in an element's Body.

    Bound once to an ``ifcopenshell`` model instance; apply to as many
    elements as needed (one column call per element, or the same mutator can
    be reused to batch-update a full storey, if desired).
    """

    def __init__(
        self,
        model: Any,
        entities_created: Optional[Dict[str, int]] = None,
    ) -> None:
        self._model = model
        self._counter = entities_created

    # ── Private helpers ──────────────────────────────────────────────────────

    def _bump(self, key: str) -> None:
        if self._counter is not None:
            self._counter[key] = int(self._counter.get(key, 0)) + 1

    def _find_body_swept_solids(self, element: Any) -> List[Any]:
        representation = getattr(element, "Representation", None)
        if representation is None:
            return []
        solids: List[Any] = []
        for shape_rep in getattr(representation, "Representations", None) or ():
            if getattr(shape_rep, "RepresentationIdentifier", None) != "Body":
                continue
            if getattr(shape_rep, "RepresentationType", None) != "SweptSolid":
                continue
            for item in getattr(shape_rep, "Items", None) or ():
                if item.is_a("IfcExtrudedAreaSolid"):
                    solids.append(item)
        return solids

    @staticmethod
    def _describe_profile(swept_area: Any) -> Dict[str, Any]:
        if swept_area is None:
            return {"profile_type": None}
        schema_name = swept_area.is_a()
        if schema_name == "IfcRectangleProfileDef":
            info: Dict[str, Any] = {
                "profile_type": PROFILE_TYPE_RECTANGLE,
                "ifc_class": schema_name,
                "x_dim": float(getattr(swept_area, "XDim", 0.0)),
                "y_dim": float(getattr(swept_area, "YDim", 0.0)),
            }
            return info
        if schema_name == "IfcRectangleHollowProfileDef":
            return {
                "profile_type": PROFILE_TYPE_RECTANGLE_HOLLOW,
                "ifc_class": schema_name,
                "x_dim": float(getattr(swept_area, "XDim", 0.0)),
                "y_dim": float(getattr(swept_area, "YDim", 0.0)),
                "wall_thickness": float(getattr(swept_area, "WallThickness", 0.0)),
            }
        if schema_name == "IfcCircleProfileDef":
            diameter = float(getattr(swept_area, "Radius", 0.0)) * 2.0
            return {
                "profile_type": PROFILE_TYPE_CIRCLE,
                "ifc_class": schema_name,
                "outer_diameter": diameter,
                "radius": float(getattr(swept_area, "Radius", 0.0)),
            }
        if schema_name == "IfcCircleHollowProfileDef":
            outer_radius = float(getattr(swept_area, "Radius", 0.0))
            wall = float(getattr(swept_area, "WallThickness", 0.0))
            return {
                "profile_type": PROFILE_TYPE_CIRCLE_HOLLOW,
                "ifc_class": schema_name,
                "outer_diameter": outer_radius * 2.0,
                "inner_diameter": max(0.0, (outer_radius - wall) * 2.0),
                "wall_thickness": wall,
                "outer_radius": outer_radius,
            }
        return {"profile_type": schema_name, "ifc_class": schema_name}

    # ── Profile instantiation helpers ────────────────────────────────────────

    def _build_profile(self, spec: ProfileSpec) -> Any:
        if spec.profile_type == PROFILE_TYPE_RECTANGLE:
            profile = self._model.create_entity(
                "IfcRectangleProfileDef",
                ProfileType="AREA",
                XDim=float(spec.width),
                YDim=float(spec.depth),
            )
            self._bump("IfcRectangleProfileDef")
            return profile
        if spec.profile_type == PROFILE_TYPE_RECTANGLE_HOLLOW:
            profile = self._model.create_entity(
                "IfcRectangleHollowProfileDef",
                ProfileType="AREA",
                XDim=float(spec.width),
                YDim=float(spec.depth),
                WallThickness=float(spec.wall_thickness or 0.0),
            )
            self._bump("IfcRectangleHollowProfileDef")
            return profile
        if spec.profile_type == PROFILE_TYPE_CIRCLE:
            profile = self._model.create_entity(
                "IfcCircleProfileDef",
                ProfileType="AREA",
                Radius=float(spec.outer_diameter) / 2.0,
            )
            self._bump("IfcCircleProfileDef")
            return profile
        # CIRCLE_HOLLOW:
        outer_radius = float(spec.outer_diameter) / 2.0
        if spec.inner_diameter is not None:
            inner_radius = float(spec.inner_diameter) / 2.0
            wall = outer_radius - inner_radius
        else:
            wall = float(spec.wall_thickness or 0.0)
        profile = self._model.create_entity(
            "IfcCircleHollowProfileDef",
            ProfileType="AREA",
            Radius=outer_radius,
            WallThickness=wall,
        )
        self._bump("IfcCircleHollowProfileDef")
        return profile

    # ── Public API ───────────────────────────────────────────────────────────

    def get_current_profile_info(self, element: Any) -> Dict[str, Any]:
        """Return a plain ``dict`` describing the element's current Body swept section.

        Keys: ``solids_found`` (int), ``bodies`` (list of per-solid dicts:
        ``current_profile`` + ``depth`` + ``position_location``).  A ``None``
        return in nested fields means the schema type was not one of the
        four ProfileSpec types -- still reported, just not directly
        re-settable via :meth:`apply_profile`.
        """
        solids = self._find_body_swept_solids(element)
        bodies: List[Dict[str, Any]] = []
        for solid in solids:
            swept = getattr(solid, "SweptArea", None)
            depth = float(getattr(solid, "Depth", 0.0))
            pos = getattr(solid, "Position", None)
            loc = getattr(getattr(pos, "Location", None), "Coordinates", None)
            bodies.append(
                {
                    "current_profile": self._describe_profile(swept),
                    "depth": depth,
                    "position_location": tuple(float(c) for c in loc) if loc else None,
                    "ifc_entity_id": int(getattr(solid, "id", 0) or 0),
                }
            )
        return {"solids_found": len(solids), "bodies": bodies}

    def apply_profile(self, element: Any, spec: ProfileSpec) -> Dict[str, Any]:
        """Replace ``SweptArea`` on every matching ``IfcExtrudedAreaSolid`` body.

        Preserves **all other attributes** on each existing solid --
        ``Position`` (including its RefDirection / Axis), ``Depth`` and
        ``ExtrudedDirection`` are unchanged.  Only the cross-section shape
        itself is swapped, which guarantees that structural attachments,
        storey containment, owner-history, axis-line representation and
        footprint representation all remain consistent with the pre-mutation
        state of the element.

        Returns a report dict with: ``solids_updated``, ``new_profile``,
        ``preserved_depth`` list (one per body updated), ``preserved_position``
        list, so the calling capability can include the diff in its output.
        """
        solids = self._find_body_swept_solids(element)
        if not solids:
            raise ValueError(
                f"No IfcExtrudedAreaSolid Body/SweptSolid representation found on "
                f"element {getattr(element, 'Name', element)}. Cannot mutate its profile."
            )
        new_profile = self._build_profile(spec)
        preserved_depths: List[float] = []
        preserved_positions: List[Any] = []
        for solid in solids:
            preserved_depths.append(float(getattr(solid, "Depth", 0.0)))
            preserved_positions.append(getattr(solid, "Position", None))
            solid.SweptArea = new_profile
        return {
            "solids_updated": len(solids),
            "new_profile": {
                "profile_type": spec.profile_type,
                "width": None if spec.width is None else float(spec.width),
                "depth": None if spec.depth is None else float(spec.depth),
                "outer_diameter": (
                    None if spec.outer_diameter is None else float(spec.outer_diameter)
                ),
                "inner_diameter": (
                    None if spec.inner_diameter is None else float(spec.inner_diameter)
                ),
                "wall_thickness": (
                    None if spec.wall_thickness is None else float(spec.wall_thickness)
                ),
            },
            "preserved_depths": preserved_depths,
            "preserved_positions_count": len(preserved_positions),
        }
