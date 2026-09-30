from abc import ABC, abstractmethod
from pathlib import Path


class IfcProductFederatorPort(ABC):
    """
    Brings a product a run assembled into the model the project federates.

    Federating is the moment the product stops being the project's own
    business and becomes part of what the project publishes: it is
    measured in the model's context, placed in the model's spatial
    structure, and contained in the storey that holds it.

    The product is identified by its GlobalId, so federating it again
    replaces the element the model carries instead of adding a second
    one beside it.
    """

    @abstractmethod
    def federate(
        self,
        container_path: Path,
        title: str,
        model_path: Path,
    ) -> str:
        """
        Federate the product and return the GlobalId it carries.
        """
        ...

    @abstractmethod
    def defederate(
        self,
        model_path: Path,
        global_id: str,
    ) -> bool:
        """
        Remove the product the GlobalId names from the model.

        Return True when an element was actually removed, False when the
        model carried no such product.
        """
        ...
