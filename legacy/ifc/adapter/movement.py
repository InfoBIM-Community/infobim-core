from typing import Any, ClassVar, Dict, Tuple
from pathlib import Path

from infobim.ifc.domain.port.movement import IfcElementMoverPort
from infobim.ifc.domain.exception.creation import (
    IfcElementNotFoundError,
    ObjectPlacementNotMovableError,
)


class IfcElementMover(IfcElementMoverPort):
    """
    Adds a displacement to an existing element's own placement.

    Every element ``IfcProductAssembler`` assembles carries an
    ``IfcLocalPlacement`` located at its own file's origin, related to the
    storey it is contained in once federated — the coordinate that origin
    sits at is the only thing standing between an element and where it
    is actually drawn. Moving the element is therefore reading that one
    point, adding the displacement to it, and writing it back: nothing
    the element's representation states has to change for the element to
    move, because every point the representation carries is measured
    from this same placement.

    The model is opened and written whole, exactly as
    ``IfcProductFederator`` does when it brings a product in: a placement
    is not addressable on its own, only through the file that carries it.
    """

    LOCAL_PLACEMENT_CLASS: ClassVar[str] = "IfcLocalPlacement"
    PLACEMENT_CLASS: ClassVar[str] = "IfcAxis2Placement3D"
    POINT_CLASS: ClassVar[str] = "IfcCartesianPoint"
    AXES: ClassVar[Tuple[str, str, str]] = ("x", "y", "z")

    def displace(
        self,
        model_path: Path,
        global_id: str,
        displacement: Dict[str, float],
    ) -> Dict[str, Tuple[float, float, float]]:
        import ifcopenshell

        model: Any = ifcopenshell.open(str(model_path))
        element: Any = self._element(model, global_id)
        location: Any = self._location(element, global_id)

        current: Tuple[float, float, float] = self._coordinates(location)
        moved: Tuple[float, float, float] = tuple(
            current[index] + displacement[axis]
            for index, axis in enumerate(self.AXES)
        )

        location.Coordinates = moved
        model.write(str(model_path))

        return {"from": current, "to": moved}

    @classmethod
    def _element(cls, model: Any, global_id: str) -> Any:
        try:
            return model.by_guid(global_id)
        except Exception as error:
            raise IfcElementNotFoundError(
                f"No element carrying GlobalId {global_id} was found in "
                f"{model}."
            ) from error

    @classmethod
    def _location(cls, element: Any, global_id: str) -> Any:
        placement: Any = getattr(element, "ObjectPlacement", None)
        if placement is None or placement.is_a() != cls.LOCAL_PLACEMENT_CLASS:
            raise ObjectPlacementNotMovableError(
                f"The element {global_id} carries no {cls.LOCAL_PLACEMENT_CLASS}, "
                f"so it cannot be moved by this flow."
            )

        relative: Any = getattr(placement, "RelativePlacement", None)
        if relative is None or relative.is_a() != cls.PLACEMENT_CLASS:
            raise ObjectPlacementNotMovableError(
                f"The element {global_id} is not related by a "
                f"{cls.PLACEMENT_CLASS}, so it cannot be moved by this flow."
            )

        location: Any = getattr(relative, "Location", None)
        if location is None or location.is_a() != cls.POINT_CLASS:
            raise ObjectPlacementNotMovableError(
                f"The element {global_id} is not located by a "
                f"{cls.POINT_CLASS}, so it cannot be moved by this flow."
            )

        return location

    @classmethod
    def _coordinates(cls, location: Any) -> Tuple[float, float, float]:
        coordinates: Any = getattr(location, "Coordinates", None)
        if (
            not isinstance(coordinates, (tuple, list))
            or len(coordinates) != len(cls.AXES)
        ):
            raise ObjectPlacementNotMovableError(
                f"The placement's own point states {coordinates!r}, which "
                f"is not one coordinate per axis."
            )

        return tuple(float(coordinate) for coordinate in coordinates)
