from typing import Any, ClassVar, Dict, List, Optional, Tuple
from uuid import NAMESPACE_URL, uuid5
from pathlib import Path

from infobim.ifc.adapter.geometry_state import GeometricProductState
from infobim.ifc.domain.port.product import IfcProductAssemblerPort
from infobim.project.adapter.contract import ProjectGuard
from infobim.ifc.domain.exception.creation import IfcCreationError


class IfcProductAssembler(IfcProductAssemblerPort):
    """
    Assembles one IFC element carrying the geometry a run created.

    The element is the product the title names: an entity of the class
    the run asked for, carrying an ``IfcProductDefinitionShape`` whose
    representation is the one the geometry state produced. What makes
    this the moment the geometry stops being loose is exactly that
    ownership — before it, a block was an item nothing referenced.

    The geometry is copied into the element's own file rather than
    referenced across files: an entity belongs to the file it was read
    from, so a representation of another file is not something this one
    may point at. The copy carries its representation context with it,
    because the item is measured in that context and would mean
    something else without it.

    The GlobalId is derived from the project and the title rather than
    minted fresh, so assembling the same product again is the same
    product, and federating it twice updates one element instead of
    leaving two. An element is written into the project's state, never
    into the model the project federates: that is the state after this
    one.
    """

    SHAPE_REPRESENTATION_CLASS: ClassVar[str] = "IfcShapeRepresentation"
    PRODUCT_DEFINITION_CLASS: ClassVar[str] = "IfcProductDefinitionShape"
    LOCAL_PLACEMENT_CLASS: ClassVar[str] = "IfcLocalPlacement"
    PLACEMENT_CLASS: ClassVar[str] = "IfcAxis2Placement3D"
    POINT_CLASS: ClassVar[str] = "IfcCartesianPoint"
    ORIGIN: ClassVar[tuple] = (0.0, 0.0, 0.0)

    def assemble(
        self,
        container_path: Path,
        title: str,
        ifc_class: str,
        attributes: Dict[str, Any],
        position: Optional[Dict[str, float]] = None,
    ) -> str:
        import ifcopenshell

        geometry: Any = GeometricProductState.read(
            GeometricProductState.path_of(
                container_path,
                title,
                GeometricProductState.GEOMETRY_FILE_NAME,
            )
        )
        shape: Any = self._shape_representation(geometry)

        element_model: Any = ifcopenshell.file(schema=geometry.schema_identifier)
        representation: Any = element_model.add(shape)
        definition: Any = element_model.create_entity(
            self.PRODUCT_DEFINITION_CLASS,
            Representations=[representation],
        )
        global_id: str = self.global_id_of(container_path, title)

        try:
            element_model.create_entity(
                ifc_class,
                GlobalId=global_id,
                Name=title,
                ObjectPlacement=self._placement(element_model, position),
                Representation=definition,
                **attributes,
            )
        except Exception as error:
            raise IfcCreationError(
                f"The product '{title}' could not be created as {ifc_class} "
                f"with {attributes}: {error}."
            ) from error

        GeometricProductState.write(
            element_model,
            GeometricProductState.path_of(
                container_path,
                title,
                GeometricProductState.ELEMENT_FILE_NAME,
            ),
        )

        return global_id

    @classmethod
    def global_id_of(cls, container_path: Path, title: str) -> str:
        """
        Return the GlobalId the product of this title carries.

        Derived from the project's own IfcProject and the title, so it is
        the same on every run: a product assembled twice is one product,
        and what federates it updates an element instead of adding a
        second one beside it.
        """
        import ifcopenshell.guid

        project_global_id: Optional[str] = ProjectGuard.ifc_project_global_id(
            container_path
        )
        if not isinstance(project_global_id, str) or not project_global_id.strip():
            raise IfcCreationError(
                f"The project at {container_path} declares no readable "
                f"IfcProject GlobalId, so its products cannot be identified."
            )

        seed: str = f"{project_global_id.strip()}/{title.strip()}"

        return ifcopenshell.guid.compress(uuid5(NAMESPACE_URL, seed).hex)

    @classmethod
    def _shape_representation(cls, geometry: Any) -> Any:
        """
        Return the representation the geometry state produced.
        """
        representations: List[Any] = list(
            geometry.by_type(cls.SHAPE_REPRESENTATION_CLASS)
        )
        if len(representations) != 1:
            raise IfcCreationError(
                f"The geometry assembled for this product carries "
                f"{len(representations)} shape representations, and a product "
                f"is given exactly one."
            )

        return representations[0]

    @classmethod
    def _placement(
        cls,
        element_model: Any,
        position: Optional[Dict[str, float]] = None,
    ) -> Any:
        """
        Return the element's own placement.

        The geometry carried by the element is expressed in the
        element's local coordinate system, so the element's placement
        is what translates that local system to where the product
        actually sits. When ``position`` is given it must map ``x``,
        ``y`` and ``z`` to finite floats; when omitted the element is
        placed at the origin of whatever parent placement later takes
        it in. Relating this placement to the spatial structure of the
        federated model is the business of whoever federates it.
        """
        if position is None:
            coordinates: Tuple[float, float, float] = cls.ORIGIN
        else:
            coordinates = (
                float(position["x"]),
                float(position["y"]),
                float(position["z"]),
            )
        location: Any = element_model.create_entity(
            cls.POINT_CLASS,
            Coordinates=coordinates,
        )
        axes: Any = element_model.create_entity(
            cls.PLACEMENT_CLASS,
            Location=location,
        )

        return element_model.create_entity(
            cls.LOCAL_PLACEMENT_CLASS,
            RelativePlacement=axes,
        )
