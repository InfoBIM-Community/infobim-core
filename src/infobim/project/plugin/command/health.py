from typing import Any, ClassVar, Dict, List, Type

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.cli.domain.response.command import HealthCheckCommandResponse
from ontobdc.container.plugin.command.health import ContainerHealthCommand

from infobim.project.adapter.proxy import ContainerCommandProxy
from infobim.project.plugin.capability.health.project import (
    ProjectHealthCheckCapability,
)


class ProjectHealthCommand(ContainerCommandProxy):
    """
    Reports the health of a project, which is more than its container's.

    Selection and validation are the container health command's, reached
    the way every project command reaches its container command. The
    report is not: a project answers for the InfoBIM contract on top of
    everything the container answers for, so this runs the project health
    capability rather than delegating the run.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="project_health",
        logical_component="project",
        description="Report the health of a registered InfoBIM Project.",
        arguments=[
            {
                "accepts": [
                    "--global-id",
                ],
                "valued": True,
                "parameter": "global_id",
                "description": (
                    "Select which project to run health checks against, "
                    "by the GlobalId carried by its IfcProject or by the "
                    "container storage identifier. When omitted, resolve "
                    "the project from the current working directory."
                ),
                "type": "str",
            },
            {
                "accepts": [
                    "--config",
                ],
                "valued": True,
                "parameter": "config",
                "description": (
                    "The config of the application, as text (YAML or "
                    "JSON). When given, health says as a warning, not as "
                    "an error, whether the project holds the constraints "
                    "it declares. When omitted, there is nothing to "
                    "compare."
                ),
                "type": "str",
            },
            {
                "accepts": ["--health"],
                "description": (
                    "Run the InfoBIM Project health check capability on "
                    "the selected project. Health compares what the "
                    "project declares in metadata, index, manifests and "
                    "its IfcProject against the files it actually holds "
                    "and reports every verification that fails."
                ),
            },
        ],
    )

    TARGET: ClassVar[Type[CliCommandPort]] = ContainerHealthCommand
    HEALTHY_KEY: ClassVar[str] = "healthy"

    HEALTHY_DESCRIPTION: ClassVar[str] = "Every verification holds."
    WARNED_DESCRIPTION: ClassVar[str] = (
        "Every verification holds, but a warning says something is worth a "
        "look. Run `infobim project --refresh` to bring the Project back in "
        "line."
    )
    UNHEALTHY_DESCRIPTION: ClassVar[str] = (
        "A verification did not hold. Run `infobim project --refresh` to "
        "bring the Project back in line with the files it holds."
    )

    def guard_project(self) -> None:
        """
        Report on a container that is not a project instead of refusing it.

        Every other project command refuses one, and should: acting on a
        container that is not a project would be acting on the wrong
        thing. This one acts on nothing — and "is this a project?" is the
        first line of what it reports, so refusing would withhold the
        answer the reader came for.
        """

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the project health report at the CLI routing stage.
        """
        target: Type[CliCommandPort] = ProjectHealthCommand.TARGET

        return ContainerCommandProxy.accepts_as_target(target, args)

    def run(self) -> HealthCheckCommandResponse:
        """
        Report every verification the project health capability runs.
        """
        report: Dict[str, Any] = CapabilityExecutor.execute(
            ProjectHealthCheckCapability(),
            self._request.context,
        )
        healthy: bool = bool(report.get(self.HEALTHY_KEY))
        # A verification that did not hold and is only a warning leaves the project healthy, and says so.
        warned: bool = any(
            not check.passed and check.warning for check in report.get("checks", [])
        )

        if not healthy:
            description, severity = self.UNHEALTHY_DESCRIPTION, "ERROR"
        elif warned:
            description, severity = self.WARNED_DESCRIPTION, "WARNING"
        else:
            description, severity = self.HEALTHY_DESCRIPTION, "SUCCESS"

        return HealthCheckCommandResponse(
            title="Project Health",
            description=description,
            content=report,
            severity=severity,
        )
