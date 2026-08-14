import os
from pathlib import Path
from typing import Iterable, Optional, Tuple

from ontobdc.cli.domain.port.context import CliContextPort, CliContextStrategyPort
from ontobdc.context.adapter.dataset_instance import DatasetEntityInstanceRepository
from ontobdc.shared.domain.model.parameter import ParameterMetadata
from ontobdc.shared.domain.port.parameter import ParameterPort
from ontobdc.storage.plugin.parameter.container import ContainerIdStrategy

from infobim.project.domain.model.contract import IFC_PROJECT_CLASS_URI, PROJECT_DATASET_NAME


class ProjectIdStrategy(ParameterPort, CliContextStrategyPort):
    """Resolve an InfoBIM Project to its IfcProject GlobalId and OntoBDC container."""

    METADATA = ParameterMetadata(
        id="org.infobim.domain.project.capability.incoming.project",
        version="0.5.0",
        name="project_id",
        description=(
            "Resolve --project-id, --project, or the current working directory "
            "to an InfoBIM Project and its underlying OntoBDC container."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        python_type=str,
    )

    @property
    def metadata(self) -> ParameterMetadata:
        return self.METADATA

    def execute(self, context: CliContextPort) -> CliContextPort:
        registered = tuple(ContainerIdStrategy._registered_containers(getattr(context, "root_path", None)))
        raw_args = getattr(context, "raw_args", None)

        selector: Optional[str] = None
        strict_id = False
        if isinstance(raw_args, list):
            if "--project-id" in raw_args:
                selector = self._value_after(raw_args, "--project-id") or self._context_value(context, "project_id")
                strict_id = True
            elif "--project" in raw_args:
                selector = self._value_after(raw_args, "--project") or self._context_value(context, "project")
            else:
                selector = self._context_value(context, "project_id")
                strict_id = selector is not None
                if selector is None:
                    selector = self._context_value(context, "project")
        else:
            selector = self._context_value(context, "project_id")
            strict_id = selector is not None
            if selector is None:
                selector = self._context_value(context, "project")

        match: Optional[Tuple[str, Path, str]]
        if selector is not None:
            match = self._find_by_project_id(selector, registered)
            if match is None and not strict_id:
                match = self._find_by_container_selector(selector, registered)
        else:
            match = self._find_from_current_path(registered)

        if match is None:
            self._clear(context)
            return context

        self._bind(context, *match)
        return context

    @classmethod
    def _find_by_project_id(
        cls,
        project_id: str,
        registered: Iterable[Tuple[str, Path]],
    ) -> Optional[Tuple[str, Path, str]]:
        normalized = str(project_id or "").strip()
        if not normalized:
            return None
        for container_id, container_path in registered:
            resolved_project_id = cls._project_id_for_container(container_path)
            if resolved_project_id == normalized:
                return container_id, container_path, resolved_project_id
        return None

    @classmethod
    def _find_by_container_selector(
        cls,
        selector: str,
        registered: Iterable[Tuple[str, Path]],
    ) -> Optional[Tuple[str, Path, str]]:
        container_match = ContainerIdStrategy._find_by_id(selector, registered)
        if container_match is None:
            container_match = ContainerIdStrategy._find_by_path(selector, registered)
        if container_match is None:
            return None
        container_id, container_path = container_match
        project_id = cls._project_id_for_container(container_path)
        if project_id is None:
            return None
        return container_id, container_path, project_id

    @classmethod
    def _find_from_current_path(
        cls,
        registered: Iterable[Tuple[str, Path]],
    ) -> Optional[Tuple[str, Path, str]]:
        container_match = ContainerIdStrategy._find_by_path(Path(os.getcwd()), registered)
        if container_match is None:
            container_match = ContainerIdStrategy._find_from_current_container()
        if container_match is None:
            return None
        container_id, container_path = container_match
        project_id = cls._project_id_for_container(container_path)
        if project_id is None:
            return None
        return container_id, container_path, project_id

    @staticmethod
    def _project_id_for_container(container_path: Path) -> Optional[str]:
        dataset_path = container_path.expanduser().resolve() / PROJECT_DATASET_NAME
        if not dataset_path.is_dir():
            return None
        try:
            payload = DatasetEntityInstanceRepository(
                dataset_path=str(dataset_path),
                entity=IFC_PROJECT_CLASS_URI,
            ).list_instances()
        except Exception:
            return None
        instances = list(payload.get("instances") or [])
        if len(instances) != 1 or not isinstance(instances[0], dict):
            return None
        row = instances[0]
        for key in ("GlobalId", "global_id", "globalId"):
            value = str(row.get(key) or "").strip()
            if value:
                return value
        return None

    @staticmethod
    def _bind(context: CliContextPort, container_id: str, container_path: Path, project_id: str) -> None:
        context.set_parameter_value("project_id", project_id)
        context.set_parameter_value("project_path", str(container_path))
        context.set_parameter_value("container_id", container_id)
        context.set_parameter_value("container_path", str(container_path))

    @staticmethod
    def _clear(context: CliContextPort) -> None:
        for name in ("project_id", "project_path", "container_id", "container_path"):
            context.delete_parameter(name)

    @staticmethod
    def _value_after(args: list[str], flag: str) -> Optional[str]:
        try:
            index = args.index(flag)
        except ValueError:
            return None
        if index + 1 >= len(args):
            return None
        value = str(args[index + 1] or "").strip()
        return value or None

    @staticmethod
    def _context_value(context: CliContextPort, name: str) -> Optional[str]:
        if not context.has_parameter(name):
            return None
        value = str(context.get_parameter_value(name) or "").strip()
        return value or None
