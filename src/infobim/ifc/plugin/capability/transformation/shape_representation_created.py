from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.ifc.domain.exception.creation import IfcCreationError
from infobim.ifc.domain.model.geometry import GeometryDefinition
from infobim.ifc.adapter.geometry_state import GeometricProductState
from infobim.ifc.plugin.machine.geometric_product_create.state import (
    GeometricProductCreateProcessState,
)


class ShapeRepresentationCreatedCapability(TransactionCapability):
    """
    Creates the IFC shape representation of the created geometry.

    It wraps the item where that item was created: in the state file of
    the product being assembled, never in the model the project
    federates. A representation whose item lives in another file is not
    something that file may reference, and a representation no product
    owns is not something the federated model should carry.

    What follows it — how the representation is assigned to a product,
    and when the assembled product enters the federated model — is not
    part of this contract and is not invented here. The states after
    this one are specified before they are added.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.ifc.plugin.capability.transformation.target."
            "shape_representation_created"
        ),
        version="0.1.0",
        name="Shape Representation Created",
        description="Create the shape representation of the created geometry.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "geometric-product", "shape_representation_created"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "container_path": {
                    "type": "string",
                    "required": True,
                    "description": "The InfoBIM project the product belongs to.",
                },
                "title": {
                    "type": "string",
                    "required": True,
                    "description": "The title of the product being assembled.",
                },
                "geometry": {
                    "type": "object",
                    "required": True,
                    "description": (
                        "The GeometryDefinition a geometry command produced "
                        "for this run."
                    ),
                    "uri": "org.infobim.ifc.geometry",
                },
            },
        },
        log_message={
            "info": {
                "en": "The shape representation of the geometry was created.",
            },
            "debug_entry": {
                "en": "Creating the shape representation of the created geometry.",
            },
        },
    )

    CONTAINER_PATH_KEY: ClassVar[str] = "container_path"
    TITLE_KEY: ClassVar[str] = "title"
    GEOMETRY_KEY: ClassVar[str] = "geometry"
    GEOMETRY_ITEM_KEY: ClassVar[str] = "geometry_item"
    STEP_ELEMENTS_KEY: ClassVar[str] = "step_elements"
    SHAPE_REPRESENTATION_KEY: ClassVar[str] = "shape_representation"
    STATE_PATH_KEY: ClassVar[str] = "geometry_state_path"
    RESULTING_STATE_KEY: ClassVar[str] = "resulting_state"

    GEOMETRY_ITEM_KIND_MAP: ClassVar[Dict[str, str]] = {
        GeometryDefinition.BOX_KIND: "SweptSolid",
        GeometryDefinition.CYLINDER_KIND: "CSG",
        GeometryDefinition.SPHERE_KIND: "CSG",
    }

    KIND_KEY: ClassVar[str] = "kind"
    PARAMETERS_KEY: ClassVar[str] = "parameters"

    BODY_IDENTIFIER: ClassVar[str] = "Body"
    MODEL_TYPE: ClassVar[str] = "Model"
    MODEL_VIEW: ClassVar[str] = "MODEL_VIEW"
    SPACE_DIMENSION: ClassVar[int] = 3
    PRECISION: ClassVar[float] = 1e-5

    def label(self, lang: str = "en") -> str:
        return GeometricProductCreateProcessState.SHAPE_REPRESENTATION_CREATED.label(lang)

    def description(self, lang: str = "en") -> str:
        return GeometricProductCreateProcessState.SHAPE_REPRESENTATION_CREATED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        geometry_kind: str = self._geometry_kind(context)
        state_path: Path = GeometricProductState.path_of(
            self._container_path(context),
            self._title(context),
            GeometricProductState.GEOMETRY_FILE_NAME,
        )
        model: Any = GeometricProductState.read(state_path)

        # Resolved in this model, not in one opened beside it: an entity
        # belongs to the file it was read from, so an item taken from
        # another handle is not something this file may reference.
        geometry_item_entity: Any = self._geometry_item(context, model)
        body_context: Any = self._body_subcontext(model)
        representation_type: str = self.GEOMETRY_ITEM_KIND_MAP.get(
            geometry_kind, "SweptSolid"
        )

        items: List[Any] = [geometry_item_entity]
        shape: Any = model.create_entity(
            "IfcShapeRepresentation",
            ContextOfItems=body_context,
            RepresentationIdentifier=self.BODY_IDENTIFIER,
            RepresentationType=representation_type,
            Items=items,
        )

        shape_reference: str = str(shape.id())
        GeometricProductState.write(model, state_path)

        context.set_parameter_value(self.SHAPE_REPRESENTATION_KEY, shape_reference)

        return {
            self.RESULTING_STATE_KEY: (
                GeometricProductCreateProcessState.SHAPE_REPRESENTATION_CREATED
            ),
            self.SHAPE_REPRESENTATION_KEY: shape_reference,
            self.STATE_PATH_KEY: str(state_path),
        }

    @classmethod
    def _container_path(cls, context: CliContextPort) -> Path:
        value: Any = context.get_parameter_value(cls.CONTAINER_PATH_KEY)
        if not isinstance(value, str) or not value.strip():
            raise IfcCreationError(
                "The InfoBIM project is missing from the command context, so "
                "the product being assembled cannot be found."
            )
        return Path(value).expanduser().resolve()

    @classmethod
    def _title(cls, context: CliContextPort) -> str:
        value: Any = context.get_parameter_value(cls.TITLE_KEY)
        if not isinstance(value, str) or not value.strip():
            raise IfcCreationError(
                "The product title is missing from the command context, so "
                "the product being assembled cannot be found."
            )
        return value.strip()

    @classmethod
    def _geometry_kind(cls, context: CliContextPort) -> str:
        if not context.has_parameter(cls.GEOMETRY_KEY):
            return GeometryDefinition.BOX_KIND
        value: Any = context.get_parameter_value(cls.GEOMETRY_KEY)
        if isinstance(value, GeometryDefinition):
            return value.kind
        if isinstance(value, dict):
            kind: Any = value.get(cls.KIND_KEY)
            if isinstance(kind, str) and kind:
                return str(kind)
        return GeometryDefinition.BOX_KIND

    @classmethod
    def _geometry_item(cls, context: CliContextPort, model: Any) -> Any:
        """
        Return the entity the geometry state created, read from this model.

        The reference the previous state left is the STEP instance number
        of the item it wrote, because a representation item is not rooted
        and has no GlobalId to be addressed by. The list of elements that
        state also leaves is the fallback, read from its end, since the
        item is the last of the entities it created.
        """
        if context.has_parameter(cls.GEOMETRY_ITEM_KEY):
            reference: Any = context.get_parameter_value(cls.GEOMETRY_ITEM_KEY)
            entity: Optional[Any] = cls._entity_of(model, reference)
            if entity is not None:
                return entity

        if context.has_parameter(cls.STEP_ELEMENTS_KEY):
            elements: Any = context.get_parameter_value(cls.STEP_ELEMENTS_KEY)
            if isinstance(elements, (list, tuple)):
                for element in reversed(elements):
                    entity = cls._entity_of(model, element)
                    if entity is not None:
                        return entity

        raise IfcCreationError(
            "No IFC geometry item (IfcBlock, IfcCylinder, IfcSphere...) was "
            "found in the command context; a representation item must exist "
            "before a shape representation can wrap it."
        )

    @staticmethod
    def _entity_of(model: Any, reference: Any) -> Optional[Any]:
        """
        Return the entity a reference names, or None when it names none.

        A STEP instance number addresses any entity of the file, rooted
        or not; a GlobalId addresses only a rooted one. Both are tried,
        because a reference written by another state is read here as what
        it is rather than as what this one expects.
        """
        if not isinstance(reference, str) or not reference.strip():
            return None

        identifier: str = reference.strip()
        if identifier.lstrip("#").isdigit():
            try:
                return model.by_id(int(identifier.lstrip("#")))
            except Exception:
                return None

        try:
            return model.by_guid(identifier)
        except Exception:
            return None

    @classmethod
    def _body_subcontext(cls, model: Any) -> Any:
        """
        Return the Body context the representation hangs from.

        The product is assembled in a file of its own, so the context is
        this file's: the one it already carries, or one created for it.
        Reconciling it with the context of the model the project
        federates belongs to whoever merges the product into that model,
        which is a step after this one.
        """
        subcontexts: List[Any] = [
            subcontext
            for subcontext in model.by_type("IfcGeometricRepresentationSubContext")
            if getattr(subcontext, "ContextIdentifier", None) == cls.BODY_IDENTIFIER
            and getattr(subcontext, "ContextType", None) == cls.MODEL_TYPE
        ]
        if len(subcontexts) > 1:
            raise IfcCreationError(
                f"The product being assembled declares "
                f"{len(subcontexts)} Body/Model representation subcontexts, "
                f"and a representation hangs from exactly one."
            )

        if subcontexts:
            return subcontexts[0]

        return model.create_entity(
            "IfcGeometricRepresentationSubContext",
            ContextIdentifier=cls.BODY_IDENTIFIER,
            ContextType=cls.MODEL_TYPE,
            ParentContext=cls._root_context(model),
            TargetView=cls.MODEL_VIEW,
        )

    @classmethod
    def _root_context(cls, model: Any) -> Any:
        """
        Return the 3D Model context of the product, creating it if absent.
        """
        contexts: List[Any] = [
            candidate
            for candidate in model.by_type("IfcGeometricRepresentationContext")
            if candidate.is_a() == "IfcGeometricRepresentationContext"
            and getattr(candidate, "ContextType", None) == cls.MODEL_TYPE
        ]
        if len(contexts) > 1:
            raise IfcCreationError(
                f"The product being assembled declares {len(contexts)} Model "
                f"representation contexts, and its geometry is measured in "
                f"exactly one."
            )

        if contexts:
            return contexts[0]

        origin: Any = model.create_entity(
            "IfcCartesianPoint",
            Coordinates=(0.0, 0.0, 0.0),
        )
        world_coordinate_system: Any = model.create_entity(
            "IfcAxis2Placement3D",
            Location=origin,
        )

        return model.create_entity(
            "IfcGeometricRepresentationContext",
            ContextType=cls.MODEL_TYPE,
            CoordinateSpaceDimension=cls.SPACE_DIMENSION,
            Precision=cls.PRECISION,
            WorldCoordinateSystem=world_coordinate_system,
        )
