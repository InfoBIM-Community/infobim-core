"""The WCS <-> paper-space mapping a paper-space VIEWPORT establishes."""

from math import cos, radians, sin
from typing import ClassVar, List

from ezdxf.math import BoundingBox2d, OCS, Vec2, Vec3
from ezdxf.entities import Viewport


class ViewportProjection:
    """
    The WCS <-> paper-space mapping a single VIEWPORT establishes.

    A VIEWPORT's view is defined in its own Display Coordinate System
    (DCS): view_target_point and view_direction_vector place the DCS in
    WCS -- the same arbitrary-axis frame OCS derives for an extrusion
    direction, centred on the target instead of the WCS origin -- and
    view_twist_angle rotates that frame's X/Y axes about the view
    direction. view_center_point (a DCS point) and view_height -- scaled
    to the viewport's own paper aspect ratio for the window's width --
    then size the visible rectangle inside that frame, and the viewport's
    own paper-space center and width/height map that rectangle onto the
    sheet.

    window() gives the WCS region a viewport frames (used to decide which
    Model geometry belongs to it), and to_paper() projects a WCS point
    into that viewport's paper-space position (used to draw that geometry
    where the viewport actually shows it). Both are only exact when the
    view has no twist; a twisted view's true rectangle is a little
    smaller than the axis-aligned box window() returns, so it can only
    ever include a bit more of Model than the viewport strictly frames,
    never less.
    """

    OVERALL_VIEWPORT_ID: ClassVar[int] = 1

    def __init__(self, viewport: Viewport) -> None:
        ocs: OCS = OCS(viewport.dxf.view_direction_vector)
        twist: float = radians(viewport.dxf.view_twist_angle)
        self._x_axis: Vec3 = ocs.ux * cos(twist) + ocs.uy * sin(twist)
        self._y_axis: Vec3 = ocs.uy * cos(twist) - ocs.ux * sin(twist)
        self._target: Vec3 = viewport.dxf.view_target_point
        self._view_center: Vec2 = Vec2(viewport.dxf.view_center_point)
        self._paper_center: Vec2 = Vec2(viewport.dxf.center)
        self._half_height: float = viewport.dxf.view_height / 2
        self._half_width: float = self._half_height * (
            viewport.dxf.width / viewport.dxf.height
        )
        self._scale: float = viewport.dxf.height / viewport.dxf.view_height

    def window(self) -> BoundingBox2d:
        """Return the WCS region this viewport frames, as an axis-aligned box."""
        corners: List[Vec3] = [
            self._target
            + self._x_axis * (self._view_center.x + dx)
            + self._y_axis * (self._view_center.y + dy)
            for dx in (-self._half_width, self._half_width)
            for dy in (-self._half_height, self._half_height)
        ]
        return BoundingBox2d(corners)

    def to_paper(self, point: Vec3) -> Vec3:
        """Project a WCS point into this viewport's paper-space position."""
        relative: Vec3 = point - self._target
        dcs: Vec2 = Vec2(relative.dot(self._x_axis), relative.dot(self._y_axis))
        paper: Vec2 = self._paper_center + (dcs - self._view_center) * self._scale
        return Vec3(paper.x, paper.y, 0.0)
