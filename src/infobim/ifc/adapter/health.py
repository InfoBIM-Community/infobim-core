from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, ClassVar, Dict, List, Optional, Tuple

from infobim.ifc.plugin.check.is_geometric_representation_context_ready.check import (
    diagnose as diagnose_geometric_representation_context_ready,
)
from infobim.ifc.plugin.check.is_ifc_model_healthy.check import (
    diagnose as diagnose_ifc_model_healthy,
)
from infobim.ifc.plugin.check.is_ifc_project_synced.check import (
    diagnose as diagnose_ifc_project_synced,
)
from infobim.ifc.plugin.check.is_object_placement_valid.check import (
    diagnose as diagnose_object_placement_valid,
)
from infobim.ifc.plugin.check.is_shape_representation_context_valid.check import (
    diagnose as diagnose_shape_representation_context_valid,
)
from infobim.ifc.plugin.check.is_spatial_structure_valid.check import (
    diagnose as diagnose_spatial_structure_valid,
)
from infobim.ifc.plugin.check.is_unit_defined.check import (
    diagnose as diagnose_unit_defined,
)


@dataclass(frozen=True)
class IfcHealthCheck:
    """
    One verification of the health of an IFC model: what it is called and
    the diagnosis that tells why the model fails it.
    """

    identifier: str
    label: str
    diagnose: Callable[..., List[str]]


class IfcModelHealthReport:
    """
    The health of IFC models, verification by verification.

    Every verification is a diagnosis of its own check package, so what this
    reports is what the checks (and the hotfixes the project refresh runs)
    decide, with the reasons the check gives.
    """

    CHECKS: ClassVar[Tuple[IfcHealthCheck, ...]] = (
        IfcHealthCheck("ifc_model_healthy", "Model declared, writable and readable", diagnose_ifc_model_healthy),
        IfcHealthCheck("ifc_project_synced", "IfcProject in sync with the project", diagnose_ifc_project_synced),
        IfcHealthCheck("unit_defined", "Units", diagnose_unit_defined),
        IfcHealthCheck(
            "geometric_representation_context_ready",
            "Geometric representation context",
            diagnose_geometric_representation_context_ready,
        ),
        IfcHealthCheck(
            "shape_representation_context_valid",
            "Shape representation contexts",
            diagnose_shape_representation_context_valid,
        ),
        IfcHealthCheck("spatial_structure_valid", "Spatial structure", diagnose_spatial_structure_valid),
        IfcHealthCheck("object_placement_valid", "Object placements", diagnose_object_placement_valid),
    )

    @classmethod
    def of(cls, project_path: Path, model_path: Path) -> List[Dict[str, Any]]:
        """
        Every verification run on the model: its identifier, label, whether it
        passed, the model it is about (its path in the project) and, when it
        did not pass, why.

        A verification that cannot run, because the IFC library fails on this
        model, does not pass and says so.
        """
        scope: str = cls._scope(project_path, model_path)
        results: List[Dict[str, Any]] = []
        check: IfcHealthCheck
        for check in cls.CHECKS:
            try:
                details: List[str] = check.diagnose(
                    project_path=str(project_path),
                    ifc_model_path=str(model_path),
                )
            except Exception as error:
                details = [f"The verification could not be run: {error}"]
            results.append(
                {
                    "identifier": check.identifier,
                    "label": check.label,
                    "passed": not details,
                    "scope": scope,
                    "details": details,
                }
            )
        return results

    @staticmethod
    def _scope(project_path: Path, model_path: Path) -> str:
        try:
            return model_path.resolve().relative_to(project_path.resolve()).as_posix()
        except ValueError:
            return str(model_path)
