"""Builders for low-level IFC geometric entities (curves, swept solids).

Each builder is deliberately small and single-responsibility:

* ``IfcCurveBuilder`` — constructs ``IfcPolyline`` / ``IfcCartesianPoint`` sequences.
* ``IfcSolidBuilder`` — constructs ``IfcExtrudedAreaSolid`` rods (rectangular
  cross-section extruded along a segment) such as reference-grid lines.

An optional ``entities_created`` counter ``dict`` is updated when provided so
callers can produce reports consistent with previous capability output.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


Point3D = Tuple[float, float, float]


class IfcCurveBuilder:
    """Create ``IfcPolyline`` / ``IfcCartesianPoint`` entities in a single model."""

    def __init__(
        self,
        model: Any,
        entities_created: Optional[Dict[str, int]] = None,
    ) -> None:
        self._model = model
        self._counter = entities_created

    def _bump(self, key: str) -> None:
        if self._counter is not None:
            self._counter[key] = int(self._counter.get(key, 0)) + 1

    def cartesian_point(self, coordinates: Tuple[float, ...]) -> Any:
        point = self._model.create_entity("IfcCartesianPoint", Coordinates=coordinates)
        self._bump("IfcCartesianPoint")
        return point

    def polyline(self, points: List[Tuple[float, ...]]) -> Any:
        """Return a new ``IfcPolyline`` connecting ``points``."""
        cartesian_points = [self.cartesian_point(p) for p in points]
        polyline = self._model.create_entity("IfcPolyline", Points=cartesian_points)
        self._bump("IfcPolyline")
        return polyline


class IfcSolidBuilder:
    """Create ``IfcExtrudedAreaSolid`` swept solids in a single model."""

    def __init__(
        self,
        model: Any,
        entities_created: Optional[Dict[str, int]] = None,
    ) -> None:
        self._model = model
        self._counter = entities_created

    def _bump(self, key: str) -> None:
        if self._counter is not None:
            self._counter[key] = int(self._counter.get(key, 0)) + 1

    def extruded_rectangular_rod(
        self,
        p1: Point3D,
        p2: Point3D,
        thickness: float,
    ) -> Any:
        """A thin axis-aligned rectangular rod running from ``p1`` to ``p2``.

        Every grid line (whether in world space or a grid's own local (u, v)
        frame) runs along a single axis, so a small lookup table is enough
        to pick an ``IfcAxis2Placement3D.RefDirection`` guaranteed not to
        be parallel to ``Axis`` — a schema requirement.
        """
        dx, dy, dz = (p2[i] - p1[i] for i in range(3))
        length = (dx * dx + dy * dy + dz * dz) ** 0.5
        if length <= 0:
            raise ValueError(f"Zero-length extruded rod between {p1} and {p2}.")
        axis_dir = (dx / length, dy / length, dz / length)

        if abs(axis_dir[0]) > 0.9 or abs(axis_dir[1]) > 0.9:
            ref_dir: Point3D = (0.0, 0.0, 1.0)
        else:
            ref_dir = (1.0, 0.0, 0.0)

        curve_builder = IfcCurveBuilder(self._model, self._counter)
        placement = self._model.create_entity(
            "IfcAxis2Placement3D",
            Location=curve_builder.cartesian_point(p1),
            Axis=self._model.create_entity("IfcDirection", DirectionRatios=axis_dir),
            RefDirection=self._model.create_entity("IfcDirection", DirectionRatios=ref_dir),
        )
        profile = self._model.create_entity(
            "IfcRectangleProfileDef",
            ProfileType="AREA",
            XDim=thickness,
            YDim=thickness,
        )
        solid = self._model.create_entity(
            "IfcExtrudedAreaSolid",
            SweptArea=profile,
            Position=placement,
            ExtrudedDirection=self._model.create_entity(
                "IfcDirection", DirectionRatios=(0.0, 0.0, 1.0)
            ),
            Depth=length,
        )
        self._bump("IfcExtrudedAreaSolid")
        return solid

    def extruded_circular_rod(
        self,
        p1: Point3D,
        p2: Point3D,
        outer_diameter: float,
        inner_diameter: Optional[float] = None,
    ) -> Any:
        """A straight circular (optionally hollow) rod running from ``p1`` to ``p2``.

        Used by pipe-segment / duct-segment builders: the swept body is a
        standard ``IfcExtrudedAreaSolid`` whose ``SweptArea`` is either an
        ``IfcCircleProfileDef`` (solid) or ``IfcCircleHollowProfileDef``
        (hollow, when ``0 < inner_diameter < outer_diameter``).  The same
        RefDirection / placement trick from
        :meth:`extruded_rectangular_rod` keeps ``Axis`` and ``RefDirection``
        non-parallel for any segment direction.
        """
        dx, dy, dz = (p2[i] - p1[i] for i in range(3))
        length = (dx * dx + dy * dy + dz * dz) ** 0.5
        if length <= 0:
            raise ValueError(f"Zero-length extruded rod between {p1} and {p2}.")
        axis_dir: Point3D = (dx / length, dy / length, dz / length)

        ax, ay, az = abs(axis_dir[0]), abs(axis_dir[1]), abs(axis_dir[2])
        if ax < ay and ax < az:
            ref_dir: Point3D = (1.0, 0.0, 0.0)
        elif ay < az:
            ref_dir = (0.0, 1.0, 0.0)
        else:
            ref_dir = (0.0, 0.0, 1.0)

        curve_builder = IfcCurveBuilder(self._model, self._counter)
        placement = self._model.create_entity(
            "IfcAxis2Placement3D",
            Location=curve_builder.cartesian_point(p1),
            Axis=self._model.create_entity("IfcDirection", DirectionRatios=axis_dir),
            RefDirection=self._model.create_entity(
                "IfcDirection", DirectionRatios=ref_dir
            ),
        )

        outer_radius = max(0.0, float(outer_diameter)) / 2.0
        inner_radius = (
            0.0 if inner_diameter is None else max(0.0, float(inner_diameter)) / 2.0
        )
        if 0 < inner_radius < outer_radius:
            profile = self._model.create_entity(
                "IfcCircleHollowProfileDef",
                ProfileType="AREA",
                Radius=outer_radius,
                WallThickness=outer_radius - inner_radius,
            )
            self._bump("IfcCircleHollowProfileDef")
        else:
            profile = self._model.create_entity(
                "IfcCircleProfileDef",
                ProfileType="AREA",
                Radius=outer_radius,
            )
            self._bump("IfcCircleProfileDef")

        solid = self._model.create_entity(
            "IfcExtrudedAreaSolid",
            SweptArea=profile,
            Position=placement,
            ExtrudedDirection=self._model.create_entity(
                "IfcDirection", DirectionRatios=(0.0, 0.0, 1.0)
            ),
            Depth=length,
        )
        self._bump("IfcExtrudedAreaSolid")
        return solid
