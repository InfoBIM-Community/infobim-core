from typing import Any, ClassVar, Dict, List
from pathlib import Path

from infobim.ifc.adapter.geometry_state import GeometricProductState
from infobim.ifc.domain.port.federation import IfcProductFederatorPort
from infobim.ifc.domain.exception.creation import IfcCreationError


class IfcProductFederator(IfcProductFederatorPort):
    """
    Brings the product a run assembled into the model the project federates.

    What arrives is the element with everything it owns: its placement,
    its representation and the geometry that representation wraps, copied
    across because an entity belongs to the file it was read from.

    Two things the product brought from its own file are then replaced by
    the model's own, because a product of this model is measured and
    placed the way this model measures and places. Its representation is
    re-pointed at the model's Body context, and the copy of the context
    it travelled with is dropped; its placement is related to the storey
    that holds it, and the element is contained in that storey, which is
    what makes it part of the building rather than a thing that happens
    to be in the file.

    Federating the same product again replaces the element the model
    already carries, together with what only that element owned. The
    identity is the product's own GlobalId, so a run that changes the
    geometry updates one element instead of leaving the old one beside
    the new.
    """

    BODY_IDENTIFIER: ClassVar[str] = "Body"
    MODEL_TYPE: ClassVar[str] = "Model"
    SUBCONTEXT_CLASS: ClassVar[str] = "IfcGeometricRepresentationSubContext"
    CONTEXT_CLASS: ClassVar[str] = "IfcGeometricRepresentationContext"
    MODEL_VIEW: ClassVar[str] = "MODEL_VIEW"
    STOREY_CLASS: ClassVar[str] = "IfcBuildingStorey"
    CONTAINMENT_CLASS: ClassVar[str] = "IfcRelContainedInSpatialStructure"
    PRODUCT_CLASS: ClassVar[str] = "IfcProduct"

    def federate(
        self,
        container_path: Path,
        title: str,
        model_path: Path,
    ) -> str:
        import ifcopenshell

        element_model: Any = GeometricProductState.read(
            GeometricProductState.path_of(
                container_path,
                title,
                GeometricProductState.ELEMENT_FILE_NAME,
            )
        )
        product: Any = self._assembled_product(element_model)
        global_id: str = str(product.GlobalId)

        model: Any = ifcopenshell.open(str(model_path))
        self._discard_product(model, global_id)

        federated: Any = model.add(product)
        self._reuse_body_context(model, federated)
        self._place_in_storey(model, federated)

        model.write(str(model_path))

        return global_id

    def defederate(
        self,
        model_path: Path,
        global_id: str,
    ) -> bool:
        """
        Remove the product the GlobalId names from the model.

        Return True when an element was actually removed. False means the
        model does not carry that GlobalId.
        """
        import ifcopenshell

        identifier: str = global_id.strip()
        if not identifier:
            raise IfcCreationError(
                "The GlobalId of the product to defederate is empty."
            )

        model: Any = ifcopenshell.open(str(model_path))
        try:
            existing: Any = model.by_guid(identifier)
        except Exception:
            return False

        IfcProductFederator._drop_from_containment(model, existing)
        IfcProductFederator._remove_owned(
            model,
            existing,
            IfcProductFederator._shared_ids(model)
            | IfcProductFederator._placement_chain_ids(existing),
            set(),
        )
        model.write(str(model_path))
        return True

    @classmethod
    def _assembled_product(cls, element_model: Any) -> Any:
        """
        Return the one product the element state assembled.
        """
        products: List[Any] = list(element_model.by_type(cls.PRODUCT_CLASS))
        if len(products) != 1:
            raise IfcCreationError(
                f"The assembled element carries {len(products)} products, and "
                f"exactly one is federated."
            )

        return products[0]

    @classmethod
    def _discard_product(cls, model: Any, global_id: str) -> None:
        """
        Remove the element the model already carries under this identity.

        What the element alone owned goes with it — its representation,
        the items that representation wraps, its placement — because a
        representation no product owns is what this whole flow exists to
        keep out of the model. What the element only pointed at stays:
        the contexts its representation is measured in, and the placement
        of the storey its own placement hangs from.
        """
        try:
            existing: Any = model.by_guid(global_id)
        except Exception:
            return

        cls._drop_from_containment(model, existing)
        cls._remove_owned(
            model,
            existing,
            cls._shared_ids(model) | cls._placement_chain_ids(existing),
            set(),
        )

    @classmethod
    def _shared_ids(cls, model: Any) -> set:
        """
        Return what belongs to the model rather than to any one product.

        The representation contexts the project declares, and the
        subcontexts under them: a product is measured in them and never
        owns them, so removing a product never removes these.
        """
        shared: set = set()
        for project in model.by_type("IfcProject"):
            for context in list(project.RepresentationContexts or []):
                shared.add(context.id())

        for subcontext in model.by_type(cls.SUBCONTEXT_CLASS):
            parent: Any = getattr(subcontext, "ParentContext", None)
            if parent is not None and parent.id() in shared:
                shared.add(subcontext.id())

        return shared

    @staticmethod
    def _placement_chain_ids(product: Any) -> set:
        """
        Return the placements above the product's own, which it only hangs from.
        """
        chain: set = set()
        placement: Any = getattr(product, "ObjectPlacement", None)
        if placement is None:
            return chain

        current: Any = getattr(placement, "PlacementRelTo", None)
        while current is not None:
            chain.add(current.id())
            current = getattr(current, "PlacementRelTo", None)

        return chain

    @classmethod
    def _remove_owned(cls, model: Any, entity: Any, shared: set, seen: set) -> None:
        """
        Remove an entity and everything it alone brought with it.

        Ownership is read from the graph rather than from the inverse
        index, because that index is not refreshed when an attribute is
        re-pointed inside a session: asking it who still refers to an
        entity would answer with the reference just moved away. What a
        product reaches and the model does not share is the product's,
        by construction — it was copied in with it.
        """
        identifier: int = entity.id()
        if identifier == 0 or identifier in seen or identifier in shared:
            return

        seen.add(identifier)
        held: List[Any] = cls._entities_held_by(entity)
        model.remove(entity)

        for value in held:
            cls._remove_owned(model, value, shared, seen)

    @staticmethod
    def _entities_held_by(entity: Any) -> List[Any]:
        """
        Return every entity an entity names in its own attributes.
        """
        held: List[Any] = []
        for value in entity:
            if hasattr(value, "is_a") and hasattr(value, "id"):
                held.append(value)
                continue

            if isinstance(value, (list, tuple)):
                held.extend(
                    item
                    for item in value
                    if hasattr(item, "is_a") and hasattr(item, "id")
                )

        return held

    @classmethod
    def _drop_from_containment(cls, model: Any, product: Any) -> None:
        """
        Take the element out of every spatial containment naming it.
        """
        for relation in list(model.by_type(cls.CONTAINMENT_CLASS)):
            related: List[Any] = list(relation.RelatedElements or [])
            remaining: List[Any] = [
                element for element in related if element.id() != product.id()
            ]
            if len(remaining) == len(related):
                continue

            if remaining:
                relation.RelatedElements = remaining
                continue

            model.remove(relation)

    @classmethod
    def _reuse_body_context(cls, model: Any, product: Any) -> None:
        """
        Measure the product's representation in this model's own context.

        The product arrived with the context it was assembled in, a copy
        of which is now in this model beside the model's own. Two Body
        contexts is one too many, so every representation is re-pointed
        at the model's and the copies are dropped afterwards, once no
        representation names them any more.
        """
        definition: Any = getattr(product, "Representation", None)
        if definition is None:
            return

        body_context: Any = cls._body_context(model, product)
        travelled: List[Any] = []
        for representation in list(definition.Representations or []):
            previous: Any = representation.ContextOfItems
            if previous is None or previous.id() == body_context.id():
                continue

            representation.ContextOfItems = body_context
            travelled.append(previous)

        shared: set = cls._shared_ids(model)
        for context in travelled:
            cls._remove_owned(model, context, shared, set())

    @classmethod
    def _body_context(cls, model: Any, product: Any) -> Any:
        """
        Return the Body context of the model, not the one that travelled.

        A model that declares none gets one, under the Model context it
        already declares: a body representation is measured in a Body
        subcontext by contract, and creating the one the model is missing
        is deterministic and takes nothing away. A model declaring more
        than one is a different matter — which of them a product is
        measured in is not something to guess.
        """
        travelled: List[int] = cls._travelled_context_ids(product)
        candidates: List[Any] = [
            subcontext
            for subcontext in model.by_type(cls.SUBCONTEXT_CLASS)
            if getattr(subcontext, "ContextIdentifier", None) == cls.BODY_IDENTIFIER
            and getattr(subcontext, "ContextType", None) == cls.MODEL_TYPE
            and subcontext.id() not in travelled
        ]
        if len(candidates) > 1:
            raise IfcCreationError(
                f"The federated model declares {len(candidates)} Body/Model "
                f"representation subcontexts of its own, and a product is "
                f"measured in exactly one."
            )

        if candidates:
            return candidates[0]

        return model.create_entity(
            cls.SUBCONTEXT_CLASS,
            ContextIdentifier=cls.BODY_IDENTIFIER,
            ContextType=cls.MODEL_TYPE,
            ParentContext=cls._root_context(model, travelled),
            TargetView=cls.MODEL_VIEW,
        )

    @classmethod
    def _root_context(cls, model: Any, travelled: List[int]) -> Any:
        """
        Return the Model context the federated model measures geometry in.
        """
        contexts: List[Any] = [
            context
            for context in model.by_type(cls.CONTEXT_CLASS)
            if context.is_a() == cls.CONTEXT_CLASS
            and getattr(context, "ContextType", None) == cls.MODEL_TYPE
            and context.id() not in travelled
        ]
        if len(contexts) != 1:
            raise IfcCreationError(
                f"The federated model declares {len(contexts)} Model "
                f"representation contexts of its own, and its geometry is "
                f"measured in exactly one."
            )

        return contexts[0]

    @staticmethod
    def _travelled_context_ids(product: Any) -> List[int]:
        """
        Return the contexts that arrived with the product's own file.

        A subcontext travels with the context it hangs from, so the whole
        chain above it travelled too: counting only the subcontext would
        leave the copied Model context looking like one of the model's
        own, and the model would look like it declares two.
        """
        definition: Any = getattr(product, "Representation", None)
        if definition is None:
            return []

        travelled: List[int] = []
        for representation in list(definition.Representations or []):
            current: Any = representation.ContextOfItems
            while current is not None and current.id() not in travelled:
                travelled.append(current.id())
                current = getattr(current, "ParentContext", None)

        return travelled

    @classmethod
    def _place_in_storey(cls, model: Any, product: Any) -> None:
        """
        Relate the product to the storey that holds it, and contain it there.
        """
        storeys: List[Any] = list(model.by_type(cls.STOREY_CLASS))
        if len(storeys) != 1:
            raise IfcCreationError(
                f"The federated model carries {len(storeys)} building "
                f"storeys, and a product is contained in exactly one."
            )

        storey: Any = storeys[0]
        placement: Any = getattr(product, "ObjectPlacement", None)
        if placement is not None and placement.is_a() == "IfcLocalPlacement":
            placement.PlacementRelTo = storey.ObjectPlacement

        cls._contain(model, storey, product)

    @classmethod
    def _contain(cls, model: Any, storey: Any, product: Any) -> None:
        """
        Add the product to the storey's containment, creating it if absent.
        """
        import ifcopenshell.guid

        relations: List[Any] = [
            relation
            for relation in model.by_type(cls.CONTAINMENT_CLASS)
            if relation.RelatingStructure is not None
            and relation.RelatingStructure.id() == storey.id()
        ]
        if len(relations) > 1:
            raise IfcCreationError(
                f"The storey of the federated model is named by "
                f"{len(relations)} containment relationships, and its "
                f"contents are stated by exactly one."
            )

        if relations:
            related: List[Any] = list(relations[0].RelatedElements or [])
            if any(element.id() == product.id() for element in related):
                return

            relations[0].RelatedElements = related + [product]
            return

        model.create_entity(
            cls.CONTAINMENT_CLASS,
            GlobalId=ifcopenshell.guid.new(),
            RelatingStructure=storey,
            RelatedElements=[product],
        )

    @classmethod
    def federated_products(cls, model: Any) -> Dict[str, Any]:
        """
        Return the products the model carries, by GlobalId.
        """
        return {
            str(product.GlobalId): product
            for product in model.by_type(cls.PRODUCT_CLASS)
            if getattr(product, "GlobalId", None) is not None
        }
