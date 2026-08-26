from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, List, Optional, Set

from rdflib import Graph, Literal

from ontobdc.shared.adapter.util import to_pascal_case, to_snake_case
from ontobdc.storage.adapter.bootstrap import StorageBootstrap


class FacadeFieldSource(str, Enum):
    FACADE = "facade"
    IFC_SCHEMA = "ifc_schema"
    NONE = "none"


@dataclass(frozen=True)
class ElementField:
    identifier: str
    label: str
    datatype: str
    required: bool


@dataclass(frozen=True)
class ElementFieldResolution:
    source: FacadeFieldSource
    entity_uri: str
    fields: List[ElementField] = field(default_factory=list)

    @property
    def field_count(self) -> int:
        return len(self.fields)


class ElementFacadeFieldResolver:
    """Resolve the fields to fill for one entity.

    Order of preference:

    1. The dataset's own materialized ``linkset/facade.ttl`` (same file
       ``StorageElementContentAdapter`` already reads for the explorer) —
       an entity already registered with a per-dataset facade snapshot.
    2. The canonical ontology tree (``brasidatacenter/ontology/**/*_facade.ttl``,
       a local-only directory walk — see ``_resolve_from_ontology_tree``)
       — a dataset that hasn't materialized its own facade snapshot yet
       still resolves the real, tracked facade instead of falling through
       to a generic IFC schema.
    3. Only when *no* facade is declared anywhere and the entity's local
       name looks like an IFC class (starts with ``Ifc``): its official
       attribute list from IfcOpenShell's EXPRESS schema for
       ``ifc_schema`` (default ``IFC4``).

    Nothing here is guessed at or invented: a facade is read exactly as
    declared wherever it lives, and the IFC fallback is the real,
    versioned buildingSMART schema, not a hand-maintained approximation.
    """

    LINKSET_DIRECTORY_NAME: ClassVar[str] = "linkset"
    FACADE_FILE_NAME: ClassVar[str] = "facade.ttl"

    def resolve(
        self,
        *,
        dataset_path: Path,
        entity_uri: str,
        ifc_schema: str,
        ontology_root: Optional[Path] = None,
    ) -> ElementFieldResolution:
        facade_fields: List[ElementField] = self._resolve_from_facade(
            dataset_path=dataset_path,
            entity_uri=entity_uri,
        )
        if not facade_fields and ontology_root is not None:
            facade_fields = self._resolve_from_ontology_tree(
                ontology_root=ontology_root,
                entity_uri=entity_uri,
            )
        if facade_fields:
            return ElementFieldResolution(
                source=FacadeFieldSource.FACADE,
                entity_uri=entity_uri,
                fields=facade_fields,
            )

        ifc_class_name: str = to_pascal_case(self._local_name(entity_uri))
        if ifc_class_name.startswith("Ifc"):
            ifc_fields: List[ElementField] = self._resolve_from_ifc_schema(
                ifc_class_name=ifc_class_name,
                ifc_schema=ifc_schema,
            )
            if ifc_fields:
                return ElementFieldResolution(
                    source=FacadeFieldSource.IFC_SCHEMA,
                    entity_uri=entity_uri,
                    fields=ifc_fields,
                )

        return ElementFieldResolution(
            source=FacadeFieldSource.NONE,
            entity_uri=entity_uri,
            fields=[],
        )

    def _resolve_from_ontology_tree(
        self,
        *,
        ontology_root: Path,
        entity_uri: str,
    ) -> List[ElementField]:
        """Canonical facade lookup, local files only, no network access.

        A canonical per-entity facade file is named ``<entity>_facade.ttl``
        (e.g. ``ifc_work_schedule_facade.ttl``, ``work_stream_facade.ttl``
        under ``brasidatacenter/ontology/tool/**/entity/``) — a plain
        ``rglob("facade.ttl")`` (the pattern
        ``EntityVectorRepositoryAdapter`` uses, which only matches a file
        literally named ``facade.ttl``, i.e. a dataset's own materialized
        snapshot) would never find it. ``ontology_root`` here is the
        InfoBIM monorepo root, which already contains the
        ``brasidatacenter`` ontology checkout, so this is a bounded local
        directory walk — never a network fetch.
        """
        try:
            candidate_files: List[Path] = sorted(
                candidate
                for candidate in ontology_root.rglob("*facade.ttl")
                if candidate.is_file()
                and ".__ontobdc__" not in candidate.parts
            )
        except OSError:
            return []

        for candidate_file in candidate_files:
            fields: List[ElementField] = self._fields_from_facade_file(
                candidate_file, entity_uri=entity_uri
            )
            if fields:
                return fields
        return []

    def _find_facade_subject(
        self,
        graph: Graph,
        *,
        entity_uri: str,
    ) -> Optional[Any]:
        """Locate the Facade individual that targets ``entity_uri``.

        Two vocabularies are in live use for this in this codebase, in
        *opposite* directions: the canonical ``facade:`` tbox declares
        ``entity hasDataEntityFacade facade`` (entity -> facade), while a
        dataset's own materialized ``linkset/facade.ttl`` snapshot instead
        declares ``facade targetsClass entity`` (facade -> entity, no
        ``hasDataEntityFacade`` triple at all). Both are matched by local
        name so either vocabulary — or a future one that reuses either
        predicate name — resolves correctly.

        ``entity_uri`` may also be the short ``entity_identifier`` form
        (e.g. ``ifc_work_schedule``, exactly what the ``--element`` list's
        ENTITY IDENTIFIER column shows) rather than a full URI or the
        PascalCase class name (``IfcWorkSchedule``) — matching goes
        through ``_match_key``, which folds away case and separators so
        all three forms compare equal.
        """
        normalized_entity: str = self._match_key(self._local_name(entity_uri))

        for entity_subject, predicate, candidate_facade_subject in graph:
            if self._local_name(predicate) != "hasDataEntityFacade":
                continue
            if self._match_key(self._local_name(entity_subject)) == normalized_entity:
                return candidate_facade_subject

        for candidate_facade_subject, predicate, entity_object in graph:
            if self._local_name(predicate) != "targetsClass":
                continue
            if self._match_key(self._local_name(entity_object)) == normalized_entity:
                return candidate_facade_subject

        return None

    def _resolve_from_facade(
        self,
        *,
        dataset_path: Path,
        entity_uri: str,
    ) -> List[ElementField]:
        facade_path: Path = (
            StorageBootstrap.get_ontobdc_directory(dataset_path)
            / self.LINKSET_DIRECTORY_NAME
            / self.FACADE_FILE_NAME
        )
        if not facade_path.is_file():
            return []
        return self._fields_from_facade_file(facade_path, entity_uri=entity_uri)

    def _fields_from_facade_file(
        self,
        facade_path: Path,
        *,
        entity_uri: str,
    ) -> List[ElementField]:
        try:
            graph: Graph = Graph()
            graph.parse(str(facade_path), format="turtle")
        except Exception:
            return []

        facade_subject: Optional[Any] = self._find_facade_subject(
            graph, entity_uri=entity_uri
        )
        if facade_subject is None:
            return []

        fields: List[ElementField] = []
        for predicate, field_subject in graph.predicate_objects(facade_subject):
            if self._local_name(predicate) != "hasFacadeField":
                continue
            identifier: Optional[str] = self._first_literal(
                graph, field_subject, "identifier"
            )
            if not identifier:
                continue
            label: str = (
                self._first_literal(graph, field_subject, "name") or identifier
            )
            datatype_object: Optional[Any] = self._first_object(
                graph, field_subject, "fieldDatatype"
            )
            datatype: str = (
                self._local_name(datatype_object) if datatype_object else "string"
            )
            required: bool = (
                self._first_literal(graph, field_subject, "isRequired") == "true"
            )
            fields.append(
                ElementField(
                    identifier=identifier,
                    label=label,
                    datatype=datatype,
                    required=required,
                )
            )

        fields.sort(key=lambda item: item.identifier)
        return fields

    def _resolve_from_ifc_schema(
        self,
        *,
        ifc_class_name: str,
        ifc_schema: str,
    ) -> List[ElementField]:
        try:
            import ifcopenshell
        except ImportError:
            return []

        schema_definition: Any = ifcopenshell.schema_by_name(ifc_schema)
        if schema_definition is None:
            return []
        declaration: Any = schema_definition.declaration_by_name(ifc_class_name)
        if declaration is None:
            return []

        fields: List[ElementField] = []
        seen: Set[str] = set()
        for attribute in declaration.all_attributes():
            attribute_name: str = str(attribute.name()).strip()
            if not attribute_name or attribute_name in seen:
                continue
            seen.add(attribute_name)
            fields.append(
                ElementField(
                    identifier=attribute_name,
                    label=attribute_name,
                    datatype="string",
                    required=not bool(attribute.optional()),
                )
            )
        return fields

    @staticmethod
    def _local_name(value: Any) -> str:
        raw_value: str = str(value or "").strip()
        if "#" in raw_value:
            return raw_value.rsplit("#", 1)[-1]
        return raw_value.rstrip("/").rsplit("/", 1)[-1]

    @staticmethod
    def _match_key(local_name: str) -> str:
        """Fold a local name to a comparable key via the shared
        ``to_snake_case`` utility, so ``ifc_work_schedule`` and
        ``IfcWorkSchedule`` (already snake_case vs. PascalCase input)
        compare equal without a bespoke normalizer here."""
        return to_snake_case(local_name.strip())

    @staticmethod
    def _first_literal(
        graph: Graph,
        subject: Any,
        local_predicate_name: str,
    ) -> Optional[str]:
        for predicate, object_value in graph.predicate_objects(subject):
            if (
                ElementFacadeFieldResolver._local_name(predicate)
                == local_predicate_name
                and isinstance(object_value, Literal)
            ):
                text_value: str = str(object_value).strip()
                if text_value:
                    return text_value
        return None

    @staticmethod
    def _first_object(
        graph: Graph,
        subject: Any,
        local_predicate_name: str,
    ) -> Optional[Any]:
        for predicate, object_value in graph.predicate_objects(subject):
            if (
                ElementFacadeFieldResolver._local_name(predicate)
                == local_predicate_name
            ):
                return object_value
        return None
