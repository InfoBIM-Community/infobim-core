import json
from typing import Any, Dict, Optional
import hashlib
from pathlib import Path
import tempfile
from importlib.resources.abc import Traversable

from brasidatacenter.resources import iter_ontology_files

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.storage.adapter.bootstrap import StorageBootstrap

from infobim.context.adapter.taxonomy import (
    PARAMETER_KEY, CONTAINER_PATH_KEY, DXF_PATH_KEY, ETL_SEGMENTS, ONTOLOGY_FILES,
)


class KindResolutionEvent:
    """Atomic per-document evidence, invalidated by input and ontology changes."""

    @staticmethod
    def required(context: CliContextPort, key: str) -> str:
        value: Any = context.get_parameter_value(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Missing or invalid context parameter: {key}.")
        return value

    @classmethod
    def provenance(cls, context: CliContextPort) -> Dict[str, str]:
        container: Path = Path(cls.required(context, CONTAINER_PATH_KEY)).resolve()
        if not StorageBootstrap.get_container_storage_file_path(container).is_file():
            raise ValueError(f"Container metadata is missing: {container}")
        source: Path = Path(cls.required(context, DXF_PATH_KEY)).resolve()
        if not source.is_file() or source.suffix.lower() != ".dxf":
            raise ValueError(f"Invalid DXF source: {source}")
        if not source.is_relative_to(container):
            raise ValueError(f"DXF source is outside the execution container: {source}")
        kind: str = cls.required(context, PARAMETER_KEY)
        if not kind.startswith(("http://", "https://", "urn:")):
            raise ValueError("element_kind must be a resolved concept URI.")
        return {
            CONTAINER_PATH_KEY: str(container),
            "source_path": source.relative_to(container).as_posix(),
            "source_hash": hashlib.sha256(source.read_bytes()).hexdigest(),
            PARAMETER_KEY: kind,
            "ontology_hash": cls._ontology_hash(),
        }

    @staticmethod
    def _ontology_hash() -> str:
        resources: Dict[str, str] = {}
        resource: Traversable
        for resource in iter_ontology_files(suffixes=(".ttl",)):
            if resource.name in ONTOLOGY_FILES:
                resources[str(resource)] = hashlib.sha256(resource.read_bytes()).hexdigest()
        if not resources:
            raise ValueError("No kind ontologies were found.")
        # Include the complete resource set; additions and deletions invalidate evidence.
        serialized: str = json.dumps(resources, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    def path(provenance: Dict[str, str], state: str) -> Path:
        return StorageBootstrap.get_ontobdc_directory(
            Path(provenance[CONTAINER_PATH_KEY])
        ).joinpath(*ETL_SEGMENTS, provenance["source_hash"], f"{state}.json")

    @classmethod
    def read(
        cls, context: CliContextPort, state: str, version: str, output_key: str
    ) -> Optional[Dict[str, Any]]:
        provenance: Dict[str, str] = cls.provenance(context)
        path: Path = cls.path(provenance, state)
        if not path.exists():
            return None
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"ETL event must be an object: {path}")
        key: str
        for key in ("state", "version", "provenance", "output"):
            if key not in payload:
                raise ValueError(f"ETL event is missing {key}: {path}")
        if (
            payload["state"] != state
            or payload["version"] != version
            or payload["provenance"] != provenance
        ):
            return None
        output: Any = payload["output"]
        if not isinstance(output, dict) or output_key not in output:
            raise ValueError(f"ETL output is missing {output_key}: {path}")
        return payload

    @classmethod
    def write(
        cls, context: CliContextPort, state: str, version: str, output: Dict[str, Any]
    ) -> Path:
        provenance: Dict[str, str] = cls.provenance(context)
        path: Path = cls.path(provenance, state)
        StorageBootstrap.ensure_ontobdc_directory(Path(provenance[CONTAINER_PATH_KEY]))
        path.parent.mkdir(parents=True, exist_ok=True)
        payload: Dict[str, Any] = {
            "state": state, "version": version, "provenance": provenance, "output": output,
        }
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.",
            suffix=".tmp", delete=False,
        ) as stream:
            temporary: Path = Path(stream.name)
            json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
        try:
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
        return path
