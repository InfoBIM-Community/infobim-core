
from pathlib import Path
from typing import Any, ClassVar, Optional

from ontobdc.shared.domain.model.parameter import ParameterMetadata
from ontobdc.cli.domain.port.context import (
    CliContextPort,
    CliContextStrategyPort,
)


class ProjectPathStrategy(CliContextStrategyPort):
    """
    Resolves a project location for InfoBIM project commands.

    The strategy mirrors :class:`ContainerIdStrategy` resolution: explicit
    ``--project-path`` or ``--project`` values take precedence, and when
    neither flag is present the current working directory is used as the
    implicit project path. The resolved path is always bound to both
    ``project_path`` (InfoBIM origin marker) and ``container_path`` (so
    downstream container proxies receive the binding transparently).
    """

    SELECTOR_FLAGS: ClassVar[tuple] = ("--project-path", "--project")

    METADATA: ParameterMetadata = ParameterMetadata(
        id="org.infobim.project.plugin.parameter.project_path",
        version="1.0.0",
        name="project_path",
        description=(
            "Resolve an InfoBIM project path from ``--project-path``, "
            "``--project``, or the current working directory to the "
            "project container underneath it."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        python_type=str,
        tags=["infobim", "project", "path", "container"],
        supported_languages=["en", "pt-br"],
    )

    def execute(self, context: CliContextPort) -> CliContextPort:
        raw_args: list = context.raw_args or []
        explicit_value: Optional[str] = None
        idx: int = 0
        total: int = len(raw_args)
        while idx < total:
            token: Any = raw_args[idx]
            if isinstance(token, str) and token in self.SELECTOR_FLAGS:
                if idx + 1 >= total:
                    return context
                next_token: Any = raw_args[idx + 1]
                if not isinstance(next_token, str) or not next_token.strip():
                    return context
                if next_token.strip().startswith("--"):
                    return context
                explicit_value = next_token.strip()
                break
            idx += 1

        if explicit_value is not None:
            raw_value: str = explicit_value
        else:
            try:
                raw_value = str(Path.cwd().expanduser().resolve())
            except (OSError, RuntimeError, ValueError):
                return context

        try:
            project_path: Path = Path(raw_value).expanduser().resolve()
        except (OSError, RuntimeError, TypeError, ValueError):
            return context
        if not project_path.is_dir():
            return context

        context.set_parameter_value("project_path", str(project_path))
        context.set_parameter_value("container_path", str(project_path))
        return context
