from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Optional

from rdflib import Graph, Literal, URIRef


class ProjectContainerResolver:
    """Resolve an IfcProject identifier to its InfoBIM container.

    Resolution is deliberately based on project metadata, not on a parallel
    InfoBIM project/schedule relation.  The resolver accepts the project RDF
    subject itself or a literal GlobalId/identifier recorded in project.ttl.
    """

    PROJECT_FILE = Path(".__ontobdc__") / "__infobim__" / "project.ttl"

    def resolve(self, project_id: str) -> Path:
        normalized = str(project_id or "").strip()
        if not normalized:
            raise ValueError("--project-id is required.")

        candidates = list(self._candidate_containers())
        matches = [
            container
            for container in candidates
            if self._project_file_matches(container / self.PROJECT_FILE, normalized)
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ValueError(
                f"IfcProject identifier is ambiguous across {len(matches)} containers: {normalized}"
            )
        raise ValueError(f"InfoBIM project not found for IfcProject identifier: {normalized}")

    def _candidate_containers(self) -> Iterable[Path]:
        selected: list[Path] = []
        seen: set[Path] = set()

        current = Path(os.getcwd()).expanduser().resolve()
        for candidate in (current, *current.parents):
            if (candidate / self.PROJECT_FILE).is_file() and candidate not in seen:
                seen.add(candidate)
                selected.append(candidate)

        # Reuse OntoBDC's storage registry when available.  This remains a
        # discovery mechanism only; project identity is still checked against
        # the InfoBIM project metadata inside each container.
        try:
            from ontobdc.storage.plugin.parameter.container import ContainerIdStrategy

            registered = ContainerIdStrategy._registered_containers(None)
            for _, container_path in registered:
                resolved = Path(container_path).expanduser().resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                selected.append(resolved)
        except Exception:
            pass

        return tuple(selected)

    def _project_file_matches(self, project_file: Path, project_id: str) -> bool:
        if not project_file.is_file():
            return False
        graph = Graph()
        try:
            graph.parse(str(project_file), format="turtle")
        except Exception:
            return False

        expected = self._normalized_identifier(project_id)
        for subject in graph.subjects():
            if isinstance(subject, URIRef):
                if self._normalized_identifier(str(subject)) == expected:
                    return True
                if self._normalized_identifier(self._local_name(subject)) == expected:
                    return True

        for _, predicate, obj in graph:
            predicate_name = self._local_name(predicate).lower().replace("_", "")
            if predicate_name not in {"globalid", "identifier", "projectid"}:
                continue
            if isinstance(obj, (Literal, URIRef)):
                if self._normalized_identifier(str(obj)) == expected:
                    return True
        return False

    @staticmethod
    def _normalized_identifier(value: str) -> str:
        return str(value or "").strip().strip("<>").lower()

    @staticmethod
    def _local_name(value: object) -> str:
        raw = str(value)
        if "#" in raw:
            return raw.rsplit("#", 1)[-1]
        if "/" in raw:
            return raw.rstrip("/").rsplit("/", 1)[-1]
        if ":" in raw:
            return raw.rsplit(":", 1)[-1]
        return raw
