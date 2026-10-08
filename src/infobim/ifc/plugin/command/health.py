from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import HealthCheckCommandResponse

from infobim.ifc.adapter.health import IfcModelHealthReport
from infobim.project.adapter.contract import ProjectGuard
from infobim.ifc.adapter.models import IfcProjectModels


class IfcHealthCommand(CliCommandPort):
    """
    Report the health of the IFC models of a project.

    Each model goes through the verifications of ``IfcModelHealthReport``, and
    every one that fails says why. Without ``--ifc-model-path`` the models are
    all those the project's RO-Crate declares. It only reports: it repairs
    nothing.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="ifc_health",
        logical_component="ifc",
        description="Report the health of the IFC models of an InfoBIM project.",
        arguments=[
            {
                "accepts": ["--global-id"],
                "valued": True,
                "parameter": "global_id",
                "description": (
                    "Select the project by the GlobalId carried by its "
                    "IfcProject. When omitted, resolve the project from the "
                    "current working directory."
                ),
                "type": "str",
            },
            {
                "accepts": ["--health"],
                "description": (
                    "Report, model by model, which verifications of the "
                    "geometric health of an IFC model hold and why the others "
                    "do not."
                ),
                "usage": (
                    "infobim ifc --health [--global-id <project-global-id>] "
                    "[--ifc-model-path <model.ifc>]"
                ),
            },
            {
                "accepts": ["--ifc-model-path"],
                "valued": True,
                "parameter": "ifc_model_path",
                "description": (
                    "The one IFC model to report on. When omitted, every IFC "
                    "model the project declares."
                ),
                "type": "Path",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "ifc"
    HEALTH_FLAG: ClassVar[str] = "--health"
    SELECTOR_FLAG: ClassVar[str] = "--global-id"
    MODEL_PATH_FLAG: ClassVar[str] = "--ifc-model-path"
    PROJECT_PATH_KEY: ClassVar[str] = "container_path"
    MODEL_PATH_KEY: ClassVar[str] = "ifc_model_path"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the IFC health report at the CLI routing stage.
        """
        if not args or args[0] != IfcHealthCommand.COMPONENT:
            return False

        return IfcHealthCommand._matches(args[1:])

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        if not self._matches(self._request.command_args):
            return False

        project_path: Any = self._request.context.get_parameter_value(
            self.PROJECT_PATH_KEY
        )
        if not isinstance(project_path, str) or not project_path.strip():
            return False

        ProjectGuard.guard(
            Path(project_path).expanduser().resolve(),
            self._request.context.root_path,
        )

        return True

    def run(self) -> HealthCheckCommandResponse:
        context: Any = self._request.context
        project_path: Path = Path(
            str(context.get_parameter_value(self.PROJECT_PATH_KEY))
        ).expanduser().resolve()

        models: List[Path] = self._models(project_path)
        checks: List[Dict[str, Any]] = [
            result
            for model in models
            for result in IfcModelHealthReport.of(project_path, model)
        ]
        healthy: bool = all(check["passed"] for check in checks)

        return HealthCheckCommandResponse(
            title="IFC Health",
            description=(
                f"{len(models)} models: every verification holds."
                if healthy
                else "A verification did not hold."
            ),
            content={
                "healthy": healthy,
                "models": [self._scope(project_path, model) for model in models],
                "checks": checks,
            },
            severity="SUCCESS" if healthy else "ERROR",
        )

    def _models(self, project_path: Path) -> List[Path]:
        """
        The model the request names, or the models the project declares.

        Raises:
            FileNotFoundError: the named model is not a file.
            LookupError: the project's RO-Crate cannot be read.
        """
        requested: Optional[str] = self._request.context.get_parameter_value(
            self.MODEL_PATH_KEY
        )
        if isinstance(requested, str) and requested.strip():
            for candidate in (Path(requested).expanduser(), project_path / requested):
                if candidate.is_file():
                    return [candidate.resolve()]
            raise FileNotFoundError(f"{requested} is not an IFC model file.")

        declared: Optional[List[Path]] = IfcProjectModels.paths(project_path)
        if declared is None:
            raise LookupError("The project's RO-Crate could not be read.")
        return sorted(declared)

    @staticmethod
    def _scope(project_path: Path, model_path: Path) -> str:
        try:
            return model_path.relative_to(project_path).as_posix()
        except ValueError:
            return str(model_path)

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are --health, optionally with
        --global-id and --ifc-model-path, each with a value, in any order and
        none repeated.
        """
        remaining: List[str] = list(scoped_args)
        if remaining.count(IfcHealthCommand.HEALTH_FLAG) != 1:
            return False
        remaining.remove(IfcHealthCommand.HEALTH_FLAG)

        if len(remaining) % 2 != 0:
            return False
        flags: List[str] = remaining[0::2]
        values: List[str] = remaining[1::2]
        if len(set(flags)) != len(flags):
            return False
        if any(
            flag not in (IfcHealthCommand.SELECTOR_FLAG, IfcHealthCommand.MODEL_PATH_FLAG)
            for flag in flags
        ):
            return False

        return all(value.strip() and not value.startswith("--") for value in values)
