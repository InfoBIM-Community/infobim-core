from pathlib import Path
from typing import ClassVar, List

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.adapter.capability import HealthCheckCapability
from ontobdc.shared.domain.model.health import HealthCheck
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.container.plugin.capability.health.container import (
    ContainerHealthCheckCapability,
)

from infobim.project.plugin.check.is_ifc_project_ready.check import (
    main as check_ifc_project_ready,
)
from infobim.project.plugin.check.is_ifc_project_schema_ready.check import (
    main as check_ifc_project_schema_ready,
)
from infobim.project.plugin.check.is_project_dataset_ready.check import (
    main as check_project_dataset_ready,
)


class ProjectHealthCheckCapability(HealthCheckCapability):
    """
    Reports the verifications that say whether a project is in order.

    An InfoBIM project is an OntoBDC container, so what the container
    capability reports about it is reported here unchanged. What InfoBIM
    adds is the contract that makes a container a project: the reserved
    dataset it has to carry, the IfcProject that dataset has to declare,
    and an unambiguous IFC schema encoded by that IfcProject's ifcOWL type.

    Those project checks come first. A container that fails them is not a
    complete project, which is the thing a reader needs to know before
    reading anything about the container underneath.
    """

    PROJECT_PATH_KEY: ClassVar[str] = "container_path"

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id="org.infobim.project.plugin.capability.health.project_health",
        version="1.0.0",
        name="Project Health Check",
        description=(
            "Report whether a project carries the reserved InfoBIM dataset, "
            "the IfcProject it declares, a schema-specific ifcOWL type, and "
            "whether the container underneath it is itself in order."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "project", "health", "read-only"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "container_path": {
                    "type": "string",
                    "required": True,
                },
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return "Project Health Check"

    def description(self, lang: str = "en") -> str:
        return "Reports the verifications that say whether a project is in order."

    def checks(self, context: CliContextPort) -> List[HealthCheck]:
        """
        Run the project verifications, then the container ones underneath.
        """
        project_path: Path = Path(
            RequiredParameter.of(context, self.PROJECT_PATH_KEY)
        ).expanduser().resolve()
        root_path: Path = Path(context.root_path).expanduser().resolve()

        checks: List[HealthCheck] = self._project_checks(project_path, root_path)
        checks.extend(ContainerHealthCheckCapability().checks(context))

        return checks

    @staticmethod
    def _project_checks(project_path: Path, root_path: Path) -> List[HealthCheck]:
        """
        Run the verifications that make a container an InfoBIM project.
        """
        return [
            HealthCheck(
                identifier="project_dataset_ready",
                label="InfoBIM dataset",
                passed=check_project_dataset_ready(
                    project_path=str(project_path),
                    root_path=str(root_path),
                ) == 0,
            ),
            HealthCheck(
                identifier="ifc_project_ready",
                label="IfcProject",
                passed=check_ifc_project_ready(
                    project_path=str(project_path),
                ) == 0,
            ),
            HealthCheck(
                identifier="ifc_project_schema_ready",
                label="IFC schema",
                passed=check_ifc_project_schema_ready(
                    project_path=str(project_path),
                ) == 0,
            ),
        ]
