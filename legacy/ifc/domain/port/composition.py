from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional


class CanonicalIfcxModelPort(ABC):
    """
    Composes converted elements into the project's canonical IFCX model.

    The model is one internal InfoBIM artifact per project, not one file per
    converted element. A Writer returns the IFCX contribution of a single
    element and never persists it; composing those contributions into a
    model and writing that model down happens here.

    Replacement is addressed by the source IFC element identity — the
    ``element_id`` the conversion started from. What a contribution looks
    like inside the IFCX document is the concrete Writer's business, so the
    nodes a previous run contributed for an element are recorded rather than
    inferred from a node-path convention invented here.
    """

    @abstractmethod
    def path(self, project_path: Path, project_global_id: str) -> Path:
        """
        Return where the canonical IFCX model of the project is persisted.
        """
        ...

    @abstractmethod
    def merge(
        self,
        project_path: Path,
        project_global_id: str,
        element_id: str,
        contribution: Dict[str, Any],
        superseded_nodes: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Merge one element's contribution into the canonical model and persist it.

        :param superseded_nodes: nodes a previous conversion of the same
            element contributed, dropped before the new ones are added.
        :return: the node paths this contribution added, for the conversion
            record to carry into the next run.
        """
        ...


class IfcConversionStatePort(ABC):
    """
    Records that one element of one project was converted to IFCX.

    The record is per element: rerunning the same element updates its own
    record instead of accumulating unrelated ones, and what it carries is
    what the next run needs in order to replace that element's contribution.
    """

    @abstractmethod
    def read(self, project_path: Path, element_id: str) -> Optional[Dict[str, Any]]:
        """
        Return the recorded conversion state of the element, if any.
        """
        ...

    @abstractmethod
    def write(self, project_path: Path, element_id: str, state: Dict[str, Any]) -> Path:
        """
        Persist the conversion state of the element and return its path.
        """
        ...
