"""Shared helpers and conventions for the 3D InfoBIM Reference Grid.

Three conventions are defined here so the two capabilities that operate
on the grid (initial creation and later density adjustment) share a
single source of truth:

* the **naming convention** used to identify a reference grid (and its
  text-label annotations) inside an arbitrary IFC model,
* the **axis-tagging scheme** (Latin for X, ordinal for Y, Greek for Z
  with repetition-based overflow past the end of the alphabet),
* the **single-place grid builder** that materialises one named
  ``IfcGrid`` inside a plane described by a ``PlacementFrame``.

``remove_existing_reference_grids`` and ``inspect_current_*`` wrap the
read-back / teardown steps that the density-adjust capability needs to
operate on an existing grid without duplicating or orphaning geometry.
"""

import math
from string import ascii_uppercase
from typing import Any, Dict, List, Optional, Sequence, Tuple

from infobim.ifc.adapter.annotation import IfcTextAnnotationBuilder
from infobim.ifc.adapter.geometry import ModelExtents, PlacementFrame
from infobim.ifc.adapter.geometry_builder import IfcCurveBuilder, IfcSolidBuilder


GRID_NAME_XY = "InfoBIM Reference Grid - XY"
GRID_NAME_XZ = "InfoBIM Reference Grid - XZ"
GRID_NAME_YZ = "InfoBIM Reference Grid - YZ"
GRID_LABEL_OBJECT_TYPE = "GRID_REFERENCE_LABEL"
GREEK_ALPHABET: Tuple[str, ...] = tuple("αβγδεζηθικλμνξοπρστυφχψω")


GRID_NAMES: frozenset[str] = frozenset({GRID_NAME_XY, GRID_NAME_XZ, GRID_NAME_YZ})


Point3D = Tuple[float, float, float]
Span = Tuple[float, float]


def repeated_symbol_tags(symbols: Sequence[str], count: int) -> List[str]:
    """A..Z, AA..ZZ, AAA..; and equivalently α..ω, αα..ωω, ..."""
    if count < 0:
        raise ValueError("'count' cannot be negative.")
    result: List[str] = []
    repeat = 1
    while len(result) < count:
        for symbol in symbols:
            result.append(symbol * repeat)
            if len(result) == count:
                break
        repeat += 1
    return result


def axis_positions(lo: float, hi: float, spacing: float) -> List[float]:
    """Uniform grid of positions from ``lo`` to ``hi`` (inclusive) in ``spacing`` steps."""
    if spacing <= 0:
        raise ValueError("Grid spacing must be greater than zero.")
    if hi <= lo:
        return [lo]
    count = math.ceil((hi - lo) / spacing) + 1
    return [lo + i * spacing for i in range(count)]


def latin_tags(n: int) -> List[str]:
    return repeated_symbol_tags(tuple(ascii_uppercase), n)


def ordinal_tags(n: int) -> List[str]:
    return [str(i + 1) for i in range(n)]


def greek_tags(n: int) -> List[str]:
    return repeated_symbol_tags(GREEK_ALPHABET, n)


def reference_grid_names() -> frozenset[str]:
    """Return the set of ``IfcGrid.Name`` values used by the 3-plane reference grid."""
    return GRID_NAMES


# ── Inspection / read-back helpers ──────────────────────────────────────────


def current_spacing(model: Any, xy_name: str = GRID_NAME_XY) -> float:
    """Read the current spacing used by the XY plane's numbered V-axes."""
    grids = {getattr(g, "Name", None): g for g in model.by_type("IfcGrid")}
    xy = grids.get(xy_name)
    if xy is None or len(xy.VAxes or ()) < 2:
        raise ValueError(
            f"'{xy_name}' with at least 2 V-axes was not found; cannot infer the current spacing."
        )
    positions = sorted(axis.AxisCurve.Points[0].Coordinates[1] for axis in xy.VAxes)
    return positions[1] - positions[0]


def current_margin(
    model: Any,
    extents: ModelExtents,
    xy_name: str = GRID_NAME_XY,
) -> float:
    """Margin currently in use (outermost letter U-axis vs the real model extents)."""
    grids = {getattr(g, "Name", None): g for g in model.by_type("IfcGrid")}
    xy = grids.get(xy_name)
    if xy is None or not xy.UAxes:
        raise ValueError(
            f"'{xy_name}' with at least 1 U-axis was not found; cannot infer the current margin."
        )
    x_positions = [axis.AxisCurve.Points[0].Coordinates[0] for axis in xy.UAxes]
    return extents.min_x - min(x_positions)


def current_line_thickness(model: Any, xy_name: str = GRID_NAME_XY) -> float:
    """Rod cross-section currently used by the XY plane's SweptSolid body representation."""
    grids = {getattr(g, "Name", None): g for g in model.by_type("IfcGrid")}
    xy = grids.get(xy_name)
    if xy is None or not xy.Representation or not xy.Representation.Representations:
        raise ValueError(
            f"'{xy_name}' has no body representation; cannot infer the current line thickness."
        )
    items = xy.Representation.Representations[0].Items
    if not items:
        raise ValueError(
            f"'{xy_name}' body representation has no items; cannot infer the current line thickness."
        )
    return items[0].SweptArea.XDim


def remove_existing_reference_grids(model: Any) -> Dict[str, int]:
    """Remove every existing reference-grid IfcGrid + label annotations.

    Used by the density-adjust capability before it rebuilds the grid at a
    new spacing. Ensures no geometry is orphaned (curves, points, swept
    solids are removed alongside their owners via explicit teardown of
    the owned axis curves).
    """
    import ifcopenshell.api.root as root_api

    removed: Dict[str, int] = {
        "IfcGrid": 0,
        "IfcGridAxis": 0,
        "IfcAnnotation": 0,
    }

    for grid in list(model.by_type("IfcGrid")):
        if getattr(grid, "Name", None) not in GRID_NAMES:
            continue
        for axis in list(grid.UAxes or ()) + list(grid.VAxes or ()):
            curve = axis.AxisCurve
            points = list(curve.Points) if curve and curve.is_a("IfcPolyline") else []
            model.remove(axis)
            removed["IfcGridAxis"] += 1
            if curve:
                model.remove(curve)
            for point in points:
                model.remove(point)
        root_api.remove_product(model, product=grid)
        removed["IfcGrid"] += 1

    for annotation in list(model.by_type("IfcAnnotation")):
        if getattr(annotation, "ObjectType", None) != GRID_LABEL_OBJECT_TYPE:
            continue
        root_api.remove_product(model, product=annotation)
        removed["IfcAnnotation"] += 1

    return removed


# ── Single-plane grid builder (orchestration) ──────────────────────────────


def build_reference_grid_plane(
    *,
    model: Any,
    body_context: Any,
    annotation_context: Any,
    storey: Any,
    name: str,
    placement: PlacementFrame,
    u_tags: Sequence[str],
    u_positions: Sequence[float],
    v_tags: Sequence[str],
    v_positions: Sequence[float],
    u_span: Span,
    v_span: Span,
    line_thickness: float,
    entities_created: Dict[str, int],
    label_object_type: str = GRID_LABEL_OBJECT_TYPE,
) -> Any:
    """Build one named ``IfcGrid`` in the plane described by ``placement``.

    Geometry (axis curves, rod solids) is authored in the grid's own
    simple local (u, v, 0) frame; ``placement`` is what puts it into
    world space via ``IfcGrid.ObjectPlacement``. Per-axis text-label
    anchors are the one exception — they are independent world-placed
    ``IfcAnnotation`` entities, so their anchor points are converted
    through ``PlacementFrame.world_point``.

    Returns the new ``IfcGrid`` instance and updates ``entities_created``
    with counts per IFC entity type produced.
    """
    import ifcopenshell.api.geometry as geometry_api
    import ifcopenshell.api.root as root_api
    import ifcopenshell.api.spatial as spatial_api

    u_lo, u_hi = u_span
    v_lo, v_hi = v_span

    curve_builder = IfcCurveBuilder(model, entities_created)
    solid_builder = IfcSolidBuilder(model, entities_created)
    text_builder = IfcTextAnnotationBuilder(model, entities_created)

    u_axes: list[Any] = []
    all_solids: list[Any] = []
    for tag, u in zip(u_tags, u_positions):
        p1: Point3D = (u, v_lo, 0.0)
        p2: Point3D = (u, v_hi, 0.0)
        curve = curve_builder.polyline([p1, p2])
        u_axes.append(
            model.create_entity("IfcGridAxis", AxisTag=tag, AxisCurve=curve, SameSense=True)
        )
        entities_created["IfcGridAxis"] = int(entities_created.get("IfcGridAxis", 0)) + 1
        all_solids.append(solid_builder.extruded_rectangular_rod(p1, p2, line_thickness))
        text_builder.create_text_label(
            annotation_context=annotation_context,
            storey=storey,
            name=f"{name} Label {tag}",
            text=str(tag),
            location=placement.world_point(u, v_lo),
            object_type=label_object_type,
        )

    v_axes: list[Any] = []
    for tag, v in zip(v_tags, v_positions):
        p1 = (u_lo, v, 0.0)
        p2 = (u_hi, v, 0.0)
        curve = curve_builder.polyline([p1, p2])
        v_axes.append(
            model.create_entity("IfcGridAxis", AxisTag=tag, AxisCurve=curve, SameSense=True)
        )
        entities_created["IfcGridAxis"] = int(entities_created.get("IfcGridAxis", 0)) + 1
        all_solids.append(solid_builder.extruded_rectangular_rod(p1, p2, line_thickness))
        text_builder.create_text_label(
            annotation_context=annotation_context,
            storey=storey,
            name=f"{name} Label {tag}",
            text=str(tag),
            location=placement.world_point(u_lo, v),
            object_type=label_object_type,
        )

    shape_rep = model.create_entity(
        "IfcShapeRepresentation",
        ContextOfItems=body_context,
        RepresentationIdentifier="Body",
        RepresentationType="SweptSolid",
        Items=all_solids,
    )
    grid = root_api.create_entity(
        model, ifc_class="IfcGrid", name=name, predefined_type="RECTANGULAR"
    )
    grid.UAxes = u_axes
    grid.VAxes = v_axes
    grid.Representation = model.create_entity(
        "IfcProductDefinitionShape", Representations=[shape_rep]
    )
    entities_created["IfcGrid"] = int(entities_created.get("IfcGrid", 0)) + 1
    spatial_api.assign_container(model, relating_structure=storey, products=[grid])
    geometry_api.edit_object_placement(
        model, product=grid, matrix=placement.ifc_4x4_matrix()
    )
    return grid


def standard_3plane_frames(
    x_lo: float,
    y_lo: float,
) -> Tuple[PlacementFrame, PlacementFrame, PlacementFrame]:
    """Return the canonical three principal-plane placements for the 3D grid.

    XY lives at world origin with standard axes; XZ runs along the left
    edge of the XY bounding box; YZ runs along the bottom edge. Matching
    these exact placements is what allows the density-adjust capability
    to rebuild the grid after teardown and have it occupy the exact same
    3-space footprint.
    """
    xy = PlacementFrame(
        location=(0.0, 0.0, 0.0),
        u_dir=(1.0, 0.0, 0.0),
        v_dir=(0.0, 1.0, 0.0),
    )
    xz = PlacementFrame(
        location=(0.0, y_lo, 0.0),
        u_dir=(1.0, 0.0, 0.0),
        v_dir=(0.0, 0.0, 1.0),
    )
    yz = PlacementFrame(
        location=(x_lo, 0.0, 0.0),
        u_dir=(0.0, 1.0, 0.0),
        v_dir=(0.0, 0.0, 1.0),
    )
    return xy, xz, yz


def new_entity_counter() -> Dict[str, int]:
    """Empty counter dict with the canonical key set for grid creation reports."""
    return {
        "IfcGrid": 0,
        "IfcGridAxis": 0,
        "IfcPolyline": 0,
        "IfcCartesianPoint": 0,
        "IfcExtrudedAreaSolid": 0,
        "IfcAnnotation": 0,
        "IfcTextLiteral": 0,
    }
