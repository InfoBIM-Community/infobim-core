import json
from typing import Any, Dict, List, Optional, Set
from pathlib import Path
from urllib.parse import unquote

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.storage.adapter.bootstrap import StorageBootstrap
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from infobim.project.plugin.machine.project_refresh.state import (
    ProjectRefreshProcessState,
)
from infobim.project.plugin.check.is_ifc_models_refreshed.hotfix import (
    main as refresh_ifc_models,
)
from ontobdc.container.plugin.check.is_container_manifest_synced.hotfix import (
    main as sync_container_manifest,
)


_CRATE_ROOT_NODE_ID: str = "./"
_CRATE_GRAPH_KEY: str = "@graph"
_CRATE_NODE_ID_KEY: str = "@id"
_CRATE_HAS_PART_KEY: str = "hasPart"

_IFC_FILE_SUFFIXES: Set[str] = {".ifc", ".ifczip", ".ifcxml"}


class IfcModelsRefreshedCapability(TransactionCapability):
    """
    Re-validates every IFC model currently declared by the project's
    RO-Crate manifest against the five per-model integrity checks that
    define a refreshed geometric layer: model health, unit completeness,
    geometric-representation context readiness, shape-representation
    context validity, and spatial-structure integrity.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.project.plugin.capability.transformation.target."
            "ifc_models_refreshed"
        ),
        version="1.0.0",
        name="IfcModels Refreshed",
        description=(
            "Re-validate every IFC model in the refreshed project's "
            "RO-Crate manifest against the five per-model geometric "
            "integrity checks: health, units, geometric context, "
            "shape-representation context and spatial structure."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "project", "ifc", "model", "refresh"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "Every IFC model currently declared by the project's "
                    "RO-Crate manifest is re-validated against the five "
                    "per-model geometric integrity checks."
                ),
            },
            "debug_entry": {
                "en": (
                    "Re-validating per-model geometric integrity on "
                    "every IFC model declared by the project RO-Crate "
                    "manifest."
                ),
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return "IfcModels Refreshed"

    def description(self, lang: str = "en") -> str:
        return (
            "Re-validates every IFC model declared in the project's "
            "RO-Crate manifest against the five per-model geometric "
            "integrity checks after the container refresh step."
        )

    @staticmethod
    def _crate_file_ids(project_path: Path) -> Optional[Set[str]]:
        crate_file: Path = StorageBootstrap.get_container_crate_metadata_file_path(
            project_path,
        )
        if not crate_file.is_file():
            return None

        try:
            crate_data: Any = json.loads(crate_file.read_text(encoding="utf-8"))
        except Exception:
            return None

        if not isinstance(crate_data, dict):
            return None

        graph_data: Any = crate_data.get(_CRATE_GRAPH_KEY)
        if not isinstance(graph_data, list):
            return None

        for node in graph_data:
            if not isinstance(node, dict):
                continue
            if node.get(_CRATE_NODE_ID_KEY) != _CRATE_ROOT_NODE_ID:
                continue

            parts: object = node.get(_CRATE_HAS_PART_KEY)
            if parts is None:
                return set()
            if not isinstance(parts, list):
                return None

            file_ids: Set[str] = set()
            for part in parts:
                if not isinstance(part, dict):
                    continue

                part_id: object = part.get(_CRATE_NODE_ID_KEY)
                if not isinstance(part_id, str) or not part_id.strip():
                    continue

                file_ids.add(unquote(part_id.strip()))

            return file_ids

        return None

    @staticmethod
    def _ifc_model_paths(project_path: Path) -> List[Path]:
        file_ids: Optional[Set[str]] = (
            IfcModelsRefreshedCapability._crate_file_ids(project_path)
        )
        if file_ids is None:
            return []

        model_paths: List[Path] = []
        for file_id in file_ids:
            relative: Path = Path(file_id)
            if relative.is_absolute():
                continue
            if relative.suffix.lower() not in _IFC_FILE_SUFFIXES:
                continue
            absolute: Path = (project_path / relative).resolve()
            if absolute.is_file():
                model_paths.append(absolute)

        return model_paths

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        project_path_value: Any = context.get_parameter_value("container_path")
        if not isinstance(project_path_value, str) or not project_path_value.strip():
            raise ValueError(
                "The project path is missing from the command context."
            )

        project_path: Path = Path(project_path_value).expanduser().resolve()
        exit_code: int = refresh_ifc_models(
            project_path=str(project_path),
            container_path=str(project_path),
            root_path=str(context.root_path),
        )
        if exit_code != 0:
            raise RuntimeError(
                f"Failed to refresh per-model integrity for the IFC "
                f"models declared by the project at {project_path}."
            )

        if sync_container_manifest(
            container_path=str(project_path),
            root_path=str(context.root_path),
        ) != 0:
            raise RuntimeError(
                f"Failed to synchronize the project manifest after refreshing "
                f"the IFC models at {project_path}."
            )

        model_paths: List[Path] = (
            IfcModelsRefreshedCapability._ifc_model_paths(project_path)
        )

        return {
            "resulting_state": ProjectRefreshProcessState.IFC_MODELS_REFRESHED,
            "project_path": str(project_path),
            "model_count": len(model_paths),
            "models": [str(path) for path in model_paths],
        }
