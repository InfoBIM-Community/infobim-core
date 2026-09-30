from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pathlib import Path

from ontobdc.shared.domain.port.chain import ChainResponsibilityPort


class IfcProductCreateResponsibilityPort(ChainResponsibilityPort):
    """
    Contract implemented by capabilities that create one IFC class.

    A product is an element of a particular class, and what that class
    carries beyond a name and a representation is the class's own
    business — a distribution chamber says which kind of chamber it is,
    a wall says how it is made. So each class is a capability that
    recognises the class it answers for and fills what that class
    declares, and the state creating the product dispatches to none of
    them by name: the chain asks who can handle the class this run
    named, and the one that can, does.

    The inherited ``can_handle`` is the whole of the selection contract.
    """


class IfcProductAssemblerPort(ABC):
    """
    Assembles one IFC element carrying the geometry a run created.

    The element is written into a fragment of the project's state, never
    into the model the project federates: what the machine assembles
    enters that model in the state that federates it, and not before.
    """

    @abstractmethod
    def assemble(
        self,
        container_path: Path,
        title: str,
        ifc_class: str,
        attributes: Dict[str, Any],
        position: Optional[Dict[str, float]] = None,
    ) -> str:
        """
        Create the element and return the GlobalId it carries.

        ``position`` is the element's own placement in world-aligned
        coordinates (``x``, ``y``, ``z`` floats). When omitted the
        element is placed at the origin of its local coordinate system.
        """
        ...
