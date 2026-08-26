"""Positioning parameter addressing a 3D point, either directly or via reference grid.

This adapter encapsulates the *two* ways a caller can tell a capability where
to insert an object:

* **Absolute coordinates:** explicit ``x``, ``y`` and optionally ``z`` values
  (``z`` defaults to 0.0 when omitted).  Used when a caller already has a
  world-space point.
* **Reference-grid addressing:** a **``grid_ref``** string such as ``"D-7"``,
  ``"D-7-β"``, ``"AA-125"`` etc. -- following the same ``{X}-{Y}[-{Z}]``
  tagging convention defined in ``grid_reference``.  The capability then
  resolves the tag set against the three IfcGrid planes already inserted by
  the ``ReferenceGridCapability`` (XY / XZ / YZ) and picks the corresponding
  world-space coordinate.  An optional ``offset`` (``[dx, dy, dz]``) is
  *added* to the resolved point so the caller can nudge e.g. a pipe axis
  slightly away from the exact grid intersection without needing to know
  the raw coordinates in advance.

The ``GridPositioningParameter`` DTO itself is *parser-neutral* -- it only
holds the final resolved point in ``.point`` (and a ``.source`` descriptor
for traceability).  Actual resolution of a ``grid_ref`` string against a
live IFC model is performed by :func:`resolve_positioning_parameter`, which
consults the same ``IfcGrid.AxisCurve`` data structures that the reference
grid capability wrote in the first place.

All coordinate operations assume the project keeps the convention laid down
by the reference-grid capability:

* X axis  → Latin tags (A..Z, AA..ZZ, ...) on XY plane UAxes.
* Y axis  → Ordinal tags (1, 2, 3, ...)      on XY plane VAxes.
* Z axis  → Greek tags (α..ω, αα..ωω, ...)   on XZ plane VAxes.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence, Tuple

from infobim.ifc.adapter.grid_reference import (
    GRID_NAME_XY,
    GRID_NAME_XZ,
    greek_tags,
    latin_tags,
    ordinal_tags,
)


Point3D = Tuple[float, float, float]


@dataclass(frozen=True)
class GridPositioningSource:
    """Free-form trace of how :class:`GridPositioningParameter` was produced.

    Purely for reporting / logging.  ``kind`` is one of ``"absolute"`` or
    ``"grid_ref"``; the remaining fields carry the exact inputs the caller
    provided so downstream error messages can include the user's own text.
    """

    kind: str
    x: Optional[float]
    y: Optional[float]
    z: Optional[float]
    grid_ref: Optional[str]
    offset: Tuple[float, float, float]


@dataclass(frozen=True)
class GridPositioningParameter:
    """A fully-resolved world-space point with provenance.

    Capabilities accept *unresolved* inputs from the CLI/API and convert
    them into one of these DTOs as the very first step of ``execute``.
    Every subsequent builder / mutator only ever sees the concrete
    ``.point`` tuple and never has to re-implement grid-tag parsing.
    """

    point: Point3D
    source: GridPositioningSource

    @property
    def x(self) -> float:
        return self.point[0]

    @property
    def y(self) -> float:
        return self.point[1]

    @property
    def z(self) -> float:
        return self.point[2]


# ── Grid-ref string parsing ──────────────────────────────────────────────────

def _split_grid_ref(grid_ref: str) -> Tuple[str, str, Optional[str]]:
    """Split ``"D-7-β"`` / ``"D-7"`` into ``(x_tag, y_tag, z_tag | None)``."""
    normalized = (grid_ref or "").strip()
    if not normalized:
        raise ValueError("'grid_ref' cannot be empty.")
    pieces = [piece for piece in normalized.split("-") if piece]
    if len(pieces) < 2 or len(pieces) > 3:
        raise ValueError(
            f"'grid_ref' must follow the pattern X-Y[-Z]; received '{grid_ref}'."
        )
    z_tag: Optional[str] = pieces[2] if len(pieces) == 3 else None
    return pieces[0], pieces[1], z_tag


def _tag_index(ordered_tags: Sequence[str], tag: str, axis_name: str) -> int:
    try:
        return list(ordered_tags).index(tag)
    except ValueError as exc:
        raise ValueError(
            f"Tag '{tag}' not found among {axis_name} tags "
            f"(first 10 = {list(ordered_tags[:10])}); make sure the reference "
            f"grid was generated with the same tagging convention."
        ) from exc


def _axis_positions_and_tags(
    grid: Any, axis_attribute: str, axis_name: str,
) -> Tuple[list[float], list[str]]:
    """Return ``(coordinates, tags)`` for every axis on a single attribute.

    ``axis_attribute`` is ``"UAxes"`` or ``"VAxes"`` on the IfcGrid.  We
    read the first coordinate of the ``IfcGridAxis.AxisCurve.Points`` list
    (valid because reference-grid axes are straight axis-aligned polylines)
    and pair it with ``IfcGridAxis.AxisTag``.
    """
    axes = list(getattr(grid, axis_attribute, None) or ())
    if not axes:
        raise ValueError(
            f"IfcGrid '{getattr(grid, 'Name', '<unnamed>')}' has no {axis_attribute}; "
            f"the {axis_name} axis cannot be resolved."
        )
    positions: list[float] = []
    tags: list[str] = []
    for axis in axes:
        curve = getattr(axis, "AxisCurve", None)
        if curve is None or not getattr(curve, "Points", None):
            continue
        coords: Tuple[float, ...] = tuple(curve.Points[0].Coordinates)
        positions.append(coords[0] if axis_attribute == "UAxes" else coords[1])
        tags.append(str(getattr(axis, "AxisTag", "") or ""))
    if not positions:
        raise ValueError(
            f"No coordinate-bearing axes found on {axis_attribute} of the "
            f"{axis_name} reference grid."
        )
    return positions, tags


# ── Public resolution entry point ────────────────────────────────────────────

def resolve_positioning_parameter(
    model: Any,
    *,
    x: Optional[float] = None,
    y: Optional[float] = None,
    z: Optional[float] = None,
    grid_ref: Optional[str] = None,
    offset: Optional[Tuple[float, float, float]] = None,
) -> GridPositioningParameter:
    """Resolve either absolute coords OR a ``grid_ref`` into a world-space point.

    Exactly **one** of the two addressing modes must be used:

    * **absolute**  → at least ``x`` and ``y`` must be numbers; ``z`` defaults
      to ``0.0`` when omitted.
    * **grid_ref**  → a ``"{LATIN}-{ORDINAL}[-{GREEK}]"`` string (the three
      components match the XY plane UAxes / VAxes and the XZ plane VAxes
      respectively); ``z`` tag is optional, omitting it places the point on
      the XY plane (``z = 0.0``).

    In both modes an ``offset`` tuple is applied *after* resolution, so it
    can be combined with either addressing form.
    """
    if offset is None:
        off = (0.0, 0.0, 0.0)
    else:
        off = (float(offset[0]), float(offset[1]), float(offset[2]))

    if grid_ref is not None:
        if x is not None or y is not None or z is not None:
            raise ValueError(
                "Provide either 'grid_ref' or explicit x/y/z coordinates, not both."
            )
        return _resolve_from_grid_ref(model, grid_ref, off)

    if x is None or y is None:
        raise ValueError(
            "Either 'grid_ref' or the 'x' and 'y' absolute coordinates are required."
        )
    z_value = 0.0 if z is None else float(z)
    raw: Point3D = (float(x), float(y), z_value)
    point = (raw[0] + off[0], raw[1] + off[1], raw[2] + off[2])
    return GridPositioningParameter(
        point=point,
        source=GridPositioningSource(
            kind="absolute", x=float(x), y=float(y), z=z_value,
            grid_ref=None, offset=off,
        ),
    )


def _resolve_from_grid_ref(
    model: Any, grid_ref: str, offset: Tuple[float, float, float],
) -> GridPositioningParameter:
    x_tag, y_tag, z_tag = _split_grid_ref(grid_ref)

    grids = {getattr(g, "Name", None): g for g in model.by_type("IfcGrid")}
    xy = grids.get(GRID_NAME_XY)
    if xy is None:
        raise ValueError(
            f"Cannot resolve grid_ref '{grid_ref}': no IfcGrid named '{GRID_NAME_XY}' "
            f"exists. Run the Reference Grid capability before this positioning step."
        )

    x_positions, x_ifc_tags = _axis_positions_and_tags(xy, "UAxes", "X (Latin)")
    y_positions, y_ifc_tags = _axis_positions_and_tags(xy, "VAxes", "Y (Ordinal)")

    # Latim / ordinal são conhecidos pelo construtor do grid; usamos a mesma
    # convenção aqui para mapear tag → índice, mas o IfcGridAxis.AxisTag real
    # prevalece se estiver preenchido (capacidade de fallback caso o tagging
    # tenha sido manual).
    if x_tag in x_ifc_tags:
        x_idx = x_ifc_tags.index(x_tag)
    else:
        latin = latin_tags(len(x_positions))
        x_idx = _tag_index(latin, x_tag, "X (Latin)")
    if y_tag in y_ifc_tags:
        y_idx = y_ifc_tags.index(y_tag)
    else:
        ordinal = ordinal_tags(len(y_positions))
        y_idx = _tag_index(ordinal, y_tag, "Y (Ordinal)")

    world_x = x_positions[x_idx]
    world_y = y_positions[y_idx]

    # Z vem do plano XZ (não do XY) — porque o YZ é ortogonal.
    world_z = 0.0
    if z_tag is not None:
        xz = grids.get(GRID_NAME_XZ)
        if xz is None:
            raise ValueError(
                f"Cannot resolve Z tag '{z_tag}': no IfcGrid named '{GRID_NAME_XZ}'."
            )
        z_positions, z_ifc_tags = _axis_positions_and_tags(xz, "VAxes", "Z (Greek)")
        if z_tag in z_ifc_tags:
            z_idx = z_ifc_tags.index(z_tag)
        else:
            greek = greek_tags(len(z_positions))
            z_idx = _tag_index(greek, z_tag, "Z (Greek)")
        world_z = z_positions[z_idx]

    raw: Point3D = (world_x, world_y, world_z)
    point = (raw[0] + offset[0], raw[1] + offset[1], raw[2] + offset[2])
    return GridPositioningParameter(
        point=point,
        source=GridPositioningSource(
            kind="grid_ref", x=None, y=None, z=None if z_tag is None else world_z,
            grid_ref=grid_ref, offset=offset,
        ),
    )


# ── Convenience: inspect available tags ──────────────────────────────────────

def list_reference_grid_tags(model: Any) -> Dict[str, list[str]]:
    """Return ``{"x": [...], "y": [...], "z": [...]}`` for a live reference grid.

    Useful for CLI auto-completion or pre-flight diagnostics.  Missing axes
    (e.g. if the user only created a 2D grid) produce empty lists instead
    of raising.
    """
    grids = {getattr(g, "Name", None): g for g in model.by_type("IfcGrid")}
    result: Dict[str, list[str]] = {"x": [], "y": [], "z": []}
    xy = grids.get(GRID_NAME_XY)
    if xy is not None:
        _, result["x"] = _axis_positions_and_tags(xy, "UAxes", "X")
        _, result["y"] = _axis_positions_and_tags(xy, "VAxes", "Y")
        if not any(result["x"]):
            result["x"] = latin_tags(len(result["x"]) or 0)
        if not any(result["y"]):
            result["y"] = ordinal_tags(len(result["y"]) or 0)
    xz = grids.get(GRID_NAME_XZ)
    if xz is not None:
        _, result["z"] = _axis_positions_and_tags(xz, "VAxes", "Z")
        if not any(result["z"]):
            result["z"] = greek_tags(len(result["z"]) or 0)
    return result
