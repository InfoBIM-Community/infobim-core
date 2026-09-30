from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from ontobdc.cli.domain.port.context import CliContextPort, CliContextStrategyPort
from ontobdc.container.plugin.parameter.container import ContainerIdStrategy
from ontobdc.shared.domain.model.parameter import ParameterMetadata

from infobim.project.adapter.contract import ProjectGuard


class GlobalIdStrategy(CliContextStrategyPort):
    """
    Resolves the GlobalId of an IfcProject to the container that carries it.

    A user of InfoBIM names a project by the GlobalId of its IfcProject, not
    by the identifier the storage index gives the container underneath. The
    container is what every command downstream needs, so this walks the
    registered projects and binds the one whose IfcProject carries the given
    GlobalId.

    When the caller omits ``--global-id`` the strategy must still produce a
    valid binding because downstream project commands are parameterised on
    ``global_id`` and therefore never trigger the plain ``container``
    resolver. In that case the current working directory is resolved as if
    the caller had used the plain OntoBDC container resolution.
    """

    SELECTOR_FLAG: ClassVar[str] = "--global-id"

    METADATA: ParameterMetadata = ParameterMetadata(
        id="org.infobim.project.plugin.parameter.global_id",
        version="1.0.0",
        name="global_id",
        description=(
            "Resolve the GlobalId of an IfcProject to the InfoBIM project "
            "that carries it, and to the container underneath it."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        python_type=str,
        tags=["infobim", "project", "identifier"],
        supported_languages=["en", "pt-br"],
    )

    def execute(self, context: CliContextPort) -> CliContextPort:
        """
        Bind the project the given GlobalId names, or clear a stale binding,
        or fall back to the current directory when the flag was not used.
        """
        if self.SELECTOR_FLAG not in context.raw_args:
            ContainerIdStrategy().execute(context)
            return context

        global_id: Optional[str] = self._selector(context)
        if global_id is None:
            self._clear(context)
            return context

        match: Optional[Tuple[str, Path]] = self._find_by_global_id(
            global_id,
            context.root_path,
        )
        if match is None:
            self._clear(context)
            return context

        context.set_parameter_value("container_id", match[0])
        context.set_parameter_value("container_path", str(match[1]))

        return context

    @staticmethod
    def _selector(context: CliContextPort) -> Optional[str]:
        """
        Return the GlobalId the user typed, or None when they typed none.
        """
        value: Any = context.get_parameter_value("global_id")

        if not isinstance(value, str) or not value.strip():
            return None

        return value.strip()

    @staticmethod
    def _find_by_global_id(
        global_id: str,
        root_path: str,
    ) -> Optional[Tuple[str, Path]]:
        """
        Return the id and path of the project the given selector names.

        A user names a project by the GlobalId of its IfcProject. They also
        name it by the URI the storage index gives the container, which is
        what a user has in hand right after creating one, so both answer
        here. The URI is tried first because matching it reads no files.

        Only registered projects are searched, so a container that is not
        one is never selected by either name.
        """
        projects: List[Dict[str, Optional[str]]] = (
            ProjectGuard.registered_projects(
                root_path,
            )
        )

        project: Dict[str, Optional[str]]
        for project in projects:
            container_id: Optional[str] = project.get("id")
            location: Any = project.get("location")
            if not isinstance(container_id, str) or not container_id.strip():
                continue
            if not isinstance(location, str) or not location.strip():
                continue

            project_path: Path = Path(location).expanduser().resolve()
            if global_id == container_id.strip():
                return container_id.strip(), project_path

            if ProjectGuard.ifc_project_global_id(project_path) == global_id:
                return container_id.strip(), project_path

        return None

    @staticmethod
    def _clear(context: CliContextPort) -> None:
        """
        Drop a project resolved by an earlier invocation.

        Leaving it in place would let a command that named an unknown
        GlobalId silently operate on whatever project came before it.
        """
        context.delete_parameter("container_id")
        context.delete_parameter("container_path")
