from abc import ABC, abstractmethod
from pathlib import Path


class IfcModelBootstrapPort(ABC):
    """
    Creates the basic IFC model a project gets when it carries none.

    Basic is deliberate: the schema the project already declares, and the
    single IfcProject the project already identifies — the same GlobalId,
    never a second project inside the project. Spatial structure is not
    part of this, and units are not either, because defining them is the
    next state of the machine rather than a favour the bootstrap does.
    """

    @abstractmethod
    def create(self, project_path: Path) -> Path:
        """
        Create the project's basic IFC model and return its path.
        """
        ...
