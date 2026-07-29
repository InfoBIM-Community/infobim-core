import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from rdflib import Graph, URIRef
from rdflib.namespace import RDF, Namespace

from infobim.project.adapter.repository import ElementImportStepRepository
from infobim.project.domain.machine.import_state import ElementImportProcessState
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.context.adapter.repository import LocalContextFileResource
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class SemanticizedCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.infobim.project.plugin.capability.transformation.target.semanticized",
        version="1.0.0",
        name="Project element import transformation to Semanticized",
        description="Materialize ontology-backed semantic interpretations for grounded table headers.",
        author=["TRAE"],
        tags=["project", "import", "semanticized", "header", "semantic"],
        supported_languages=["en", "pt-br"],
    )

    _HEADER_TYPE = Namespace("http://datacenter.app.br/ontology/bsi/element/ifc_work_schedule/type.ttl#")
    _SCHEMA = Namespace("https://schema.org/")

    def label(self, lang: str = "en") -> str:
        return "Project element import transformation to Semanticized"

    def description(self, lang: str = "en") -> str:
        return "Materialize ontology-backed semantic interpretations for grounded table headers."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        step_repository: Optional[ElementImportStepRepository] = context.get_parameter_value("element_import_step_repository")
        if not isinstance(step_repository, ElementImportStepRepository):
            step_repository = ElementImportStepRepository(
                container_path=str(context.get_parameter_value("container_path")),
                source_path=str(context.get_parameter_value("import_path")),
                element_name=str(context.get_parameter_value("element_name")),
            )
            context.set_parameter_value("element_import_step_repository", step_repository)

        grounded_resource: LocalContextFileResource = step_repository.reload(ElementImportProcessState.GROUNDED)
        grounded_payload: Dict[str, Any] = json.loads(str(grounded_resource.content))
        grounded_tables: List[Dict[str, Any]] = list(grounded_payload.get("grounded_tables", []))
        if not grounded_tables:
            raise ValueError("The grounded artifact does not contain grounded tables to semanticize.")

        document_language: Dict[str, Any] = self._load_document_language(step_repository=step_repository)
        semantic_bundle: Dict[str, Any] = self._load_header_semantics(root_path=str(context.root_path))
        semantic_index: Dict[str, List[Dict[str, Any]]] = dict(semantic_bundle["semantic_index"])

        semanticized_tables: List[Dict[str, Any]] = []
        header_index: List[Dict[str, Any]] = []
        for table in grounded_tables:
            semanticized_headers: List[Dict[str, Any]] = []
            for header in list(table.get("headers", [])):
                semantic_header: Dict[str, Any] = self._semanticize_header(
                    header=header,
                    semantic_index=semantic_index,
                    document_language_code=str(document_language["code"]),
                )
                semanticized_headers.append(semantic_header)
                header_index.append(
                    {
                        "page_number": table.get("page_number"),
                        "table_index": table.get("table_index"),
                        "column_index": semantic_header.get("column_index"),
                        "header": semantic_header.get("header"),
                        "canonical_text": semantic_header.get("canonical_text"),
                        "semantic_key": semantic_header.get("semantic_key"),
                        "header_field_uri": semantic_header.get("header_field_uri"),
                        "matched_term_kind": semantic_header.get("matched_term_kind"),
                        "matched_term_uri": semantic_header.get("matched_term_uri"),
                    }
                )

            semanticized_tables.append(
                {
                    "page_number": table.get("page_number"),
                    "table_index": table.get("table_index"),
                    "table_bbox": table.get("table_bbox", []),
                    "headers": semanticized_headers,
                }
            )

        semanticized_payload: Dict[str, Any] = {
            "source_state": ElementImportProcessState.GROUNDED.value,
            "source_artifact": str(grounded_resource.path),
            "document_language": document_language,
            "vocabulary": {
                "ontology_path": semantic_bundle["ontology_path"],
                "vocabulary_uri": semantic_bundle["vocabulary_uri"],
                "supported_ifc_schemas": semantic_bundle["supported_ifc_schemas"],
            },
            "summary": {
                "table_count": len(semanticized_tables),
                "header_count": len(header_index),
                "semanticized_header_count": sum(
                    1 for item in header_index if item.get("semantic_key")
                ),
            },
            "semanticized_tables": semanticized_tables,
            "header_index": header_index,
        }
        semanticized_path = step_repository.write_text_file(
            state=ElementImportProcessState.SEMANTICIZED,
            content=json.dumps(semanticized_payload, ensure_ascii=True, indent=2, sort_keys=True),
            file_type="json",
        )
        context.set_parameter_value("resource", LocalContextFileResource(semanticized_path))
        return {
            "resulting_state": ElementImportProcessState.SEMANTICIZED,
            "path": str(semanticized_path),
            "table_count": len(semanticized_tables),
            "header_count": len(header_index),
        }

    def _semanticize_header(
        self,
        header: Dict[str, Any],
        semantic_index: Dict[str, List[Dict[str, Any]]],
        document_language_code: str,
    ) -> Dict[str, Any]:
        surface_text: str = str(header.get("header", "")).strip()
        normalized_text: str = self._normalize_text(surface_text)
        normalized_tokens: List[str] = [token for token in normalized_text.split(" ") if token]
        matched_semantic: Optional[Dict[str, Any]] = self._select_best_candidate(
            candidates=semantic_index.get(normalized_text, []),
            document_language_code=document_language_code,
        )

        if matched_semantic is None:
            canonical_text: Optional[str] = None
            canonical_tokens: List[str] = []
            semantic_key: Optional[str] = None
            semantic_label: Optional[str] = None
            semantic_source: str = "ontology_unmatched"
            preferred_label: Optional[str] = None
            preferred_label_uri: Optional[str] = None
            preferred_label_language_code: Optional[str] = None
            header_field_uri: Optional[str] = None
            matched_term_kind: Optional[str] = None
            matched_term_uri: Optional[str] = None
            matched_surface_text: Optional[str] = None
            matched_language_code: Optional[str] = None
        else:
            canonical_text = str(matched_semantic["canonical_normalized_form"]).strip() or None
            canonical_tokens = [token for token in str(canonical_text or "").split(" ") if token]
            semantic_key = matched_semantic.get("semantic_key")
            semantic_label = matched_semantic.get("semantic_label")
            semantic_source = "ontology_header_type"
            header_field_uri = matched_semantic.get("header_field_uri")
            preferred_label_payload: Optional[Dict[str, Any]] = self._select_preferred_label(
                preferred_labels=list(matched_semantic.get("preferred_labels", [])),
                document_language_code=document_language_code,
            )
            preferred_label = None if preferred_label_payload is None else preferred_label_payload.get("surface_form")
            preferred_label_uri = None if preferred_label_payload is None else preferred_label_payload.get("uri")
            preferred_label_language_code = None if preferred_label_payload is None else preferred_label_payload.get("language_code")
            matched_term_kind = matched_semantic.get("matched_term_kind")
            matched_term_uri = matched_semantic.get("matched_term_uri")
            matched_surface_text = matched_semantic.get("matched_surface_text")
            matched_language_code = matched_semantic.get("matched_language_code")

        return {
            **header,
            "surface_text": surface_text,
            "normalized_text": normalized_text,
            "normalized_tokens": normalized_tokens,
            "canonical_tokens": canonical_tokens,
            "canonical_text": canonical_text,
            "semantic_key": semantic_key,
            "semantic_label": semantic_label,
            "semantic_source": semantic_source,
            "preferred_label": preferred_label,
            "preferred_label_uri": preferred_label_uri,
            "preferred_label_language_code": preferred_label_language_code,
            "header_field_uri": header_field_uri,
            "matched_term_kind": matched_term_kind,
            "matched_term_uri": matched_term_uri,
            "matched_surface_text": matched_surface_text,
            "matched_language_code": matched_language_code,
            "document_language_code": document_language_code,
        }

    def _load_header_semantics(self, root_path: str) -> Dict[str, Any]:
        ontology_path: Path = (
            Path(root_path).expanduser().resolve()
            / "brasidatacenter"
            / "ontology"
            / "bsi"
            / "element"
            / "ifc_work_schedule"
            / "type.ttl"
        )
        if not ontology_path.exists():
            raise FileNotFoundError(f"Header type ontology not found: {ontology_path}")

        graph: Graph = Graph()
        graph.parse(str(ontology_path), format="turtle")

        vocabulary_uri: URIRef = self._HEADER_TYPE.IfcWorkScheduleHeaderVocabulary
        supported_ifc_schemas: List[Dict[str, Any]] = []
        for schema_uri in graph.objects(vocabulary_uri, self._HEADER_TYPE.supportsIfcSchema):
            supported_ifc_schemas.append(
                {
                    "uri": str(schema_uri),
                    "identifier": self._graph_literal(graph, schema_uri, self._SCHEMA.identifier),
                    "name": self._graph_literal(graph, schema_uri, self._SCHEMA.name),
                }
            )

        semantic_index: Dict[str, List[Dict[str, Any]]] = {}
        for field_uri in graph.subjects(RDF.type, self._HEADER_TYPE.HeaderField):
            preferred_labels: List[Dict[str, Any]] = []
            for preferred_label_uri in graph.objects(field_uri, self._HEADER_TYPE.hasPreferredLabel):
                preferred_label_surface: Optional[str] = self._graph_literal(graph, preferred_label_uri, self._HEADER_TYPE.surfaceForm)
                preferred_label_normalized: Optional[str] = self._graph_literal(graph, preferred_label_uri, self._HEADER_TYPE.normalizedForm)
                preferred_label_language_code: Optional[str] = self._graph_literal(graph, preferred_label_uri, self._HEADER_TYPE.languageCode)
                if not preferred_label_surface or not preferred_label_normalized or not preferred_label_language_code:
                    raise ValueError(f"Preferred header label is incomplete in ontology: {preferred_label_uri}")

                preferred_labels.append(
                    {
                        "uri": str(preferred_label_uri),
                        "surface_form": preferred_label_surface,
                        "normalized_form": preferred_label_normalized,
                        "language_code": preferred_label_language_code,
                    }
                )

            if not preferred_labels:
                raise ValueError(f"No preferred labels were declared for header field: {field_uri}")

            concept_payload: Dict[str, Any] = {
                "semantic_key": self._graph_literal(graph, field_uri, self._HEADER_TYPE.semanticKey),
                "semantic_label": self._graph_literal(graph, field_uri, self._SCHEMA.name),
                "canonical_normalized_form": self._graph_literal(graph, field_uri, self._HEADER_TYPE.canonicalNormalizedForm),
                "header_field_uri": str(field_uri),
                "preferred_labels": preferred_labels,
            }
            if not concept_payload["semantic_key"]:
                raise ValueError(f"Missing semantic key for header concept: {field_uri}")
            if not concept_payload["canonical_normalized_form"]:
                raise ValueError(f"Missing canonical normalized form for header concept: {field_uri}")

            for preferred_label in preferred_labels:
                self._register_semantic_term(
                    semantic_index=semantic_index,
                    term_normalized=str(preferred_label["normalized_form"]),
                    concept_payload=concept_payload,
                    matched_term_kind="preferred_label",
                    matched_term_uri=str(preferred_label["uri"]),
                    matched_surface_text=str(preferred_label["surface_form"]),
                    matched_language_code=str(preferred_label["language_code"]),
                )

            for alias_uri in graph.objects(field_uri, self._HEADER_TYPE.hasObservedAlias):
                alias_surface: Optional[str] = self._graph_literal(graph, alias_uri, self._HEADER_TYPE.surfaceForm)
                alias_normalized: Optional[str] = self._graph_literal(graph, alias_uri, self._HEADER_TYPE.normalizedForm)
                alias_language_code: Optional[str] = self._graph_literal(graph, alias_uri, self._HEADER_TYPE.languageCode)
                if not alias_surface or not alias_normalized or not alias_language_code:
                    raise ValueError(f"Observed header alias is incomplete in ontology: {alias_uri}")

                self._register_semantic_term(
                    semantic_index=semantic_index,
                    term_normalized=alias_normalized,
                    concept_payload=concept_payload,
                    matched_term_kind="observed_alias",
                    matched_term_uri=str(alias_uri),
                    matched_surface_text=alias_surface,
                    matched_language_code=alias_language_code,
                )

        if not semantic_index:
            raise ValueError(f"No header semantics were loaded from ontology: {ontology_path}")

        return {
            "ontology_path": str(ontology_path),
            "vocabulary_uri": str(vocabulary_uri),
            "supported_ifc_schemas": supported_ifc_schemas,
            "semantic_index": semantic_index,
        }

    def _register_semantic_term(
        self,
        semantic_index: Dict[str, List[Dict[str, Any]]],
        term_normalized: str,
        concept_payload: Dict[str, Any],
        matched_term_kind: str,
        matched_term_uri: str,
        matched_surface_text: str,
        matched_language_code: str,
    ) -> None:
        normalized_key: str = term_normalized.strip()
        if not normalized_key:
            raise ValueError("Header term normalized form cannot be empty.")

        semantic_index.setdefault(normalized_key, [])
        for existing_term in semantic_index[normalized_key]:
            if (
                existing_term.get("header_field_uri") == concept_payload.get("header_field_uri")
                and existing_term.get("matched_term_uri") == matched_term_uri
            ):
                return
            if (
                existing_term.get("header_field_uri") != concept_payload.get("header_field_uri")
                and self._language_primary_tag(str(existing_term.get("matched_language_code") or ""))
                == self._language_primary_tag(matched_language_code)
            ):
                raise ValueError(
                    f"Header term '{normalized_key}' is ambiguously mapped to multiple concepts for the same language."
                )

        semantic_index[normalized_key].append(
            {
                **concept_payload,
                "matched_term_kind": matched_term_kind,
                "matched_term_uri": matched_term_uri,
                "matched_surface_text": matched_surface_text,
                "matched_language_code": matched_language_code,
            }
        )

    def _load_document_language(self, step_repository: ElementImportStepRepository) -> Dict[str, Any]:
        localized_resource: LocalContextFileResource = step_repository.reload(ElementImportProcessState.LOCALIZED)
        localized_payload: Dict[str, Any] = json.loads(str(localized_resource.content))
        language_payload: object = localized_payload.get("language")
        if not isinstance(language_payload, dict):
            raise ValueError("The localized artifact does not contain a valid language payload.")

        language_code: object = language_payload.get("code")
        if not isinstance(language_code, str) or not language_code.strip():
            raise ValueError("The localized artifact does not contain a valid document language code.")

        language_score: object = language_payload.get("score")
        return {
            "code": language_code.strip().lower(),
            "score": None if language_score is None else float(language_score),
            "source_artifact": str(localized_resource.path),
        }

    def _select_best_candidate(
        self,
        candidates: Sequence[Dict[str, Any]],
        document_language_code: str,
    ) -> Optional[Dict[str, Any]]:
        if not candidates:
            return None

        ranked_candidates: List[tuple[tuple[int, int], Dict[str, Any]]] = []
        for candidate in candidates:
            language_rank: int = self._language_rank(
                document_language_code=document_language_code,
                candidate_language_code=str(candidate.get("matched_language_code") or ""),
            )
            term_kind_rank: int = 1 if candidate.get("matched_term_kind") == "preferred_label" else 0
            ranked_candidates.append(((language_rank, term_kind_rank), candidate))

        ranked_candidates.sort(key=lambda item: item[0], reverse=True)
        return ranked_candidates[0][1]

    def _select_preferred_label(
        self,
        preferred_labels: Sequence[Dict[str, Any]],
        document_language_code: str,
    ) -> Optional[Dict[str, Any]]:
        if not preferred_labels:
            return None

        ranked_labels: List[tuple[int, Dict[str, Any]]] = []
        for preferred_label in preferred_labels:
            language_rank: int = self._language_rank(
                document_language_code=document_language_code,
                candidate_language_code=str(preferred_label.get("language_code") or ""),
            )
            ranked_labels.append((language_rank, dict(preferred_label)))

        ranked_labels.sort(key=lambda item: item[0], reverse=True)
        return ranked_labels[0][1]

    def _language_rank(self, document_language_code: str, candidate_language_code: str) -> int:
        document_primary: str = self._language_primary_tag(document_language_code)
        candidate_primary: str = self._language_primary_tag(candidate_language_code)
        if document_primary and candidate_primary and document_primary == candidate_primary:
            return 2
        if not candidate_primary:
            return 1
        return 0

    def _language_primary_tag(self, language_code: str) -> str:
        normalized_language_code: str = str(language_code or "").strip().lower()
        if not normalized_language_code:
            return ""

        return normalized_language_code.split("-")[0]

    def _graph_literal(self, graph: Graph, subject: URIRef, predicate: URIRef) -> Optional[str]:
        value = graph.value(subject, predicate)
        if value is None:
            return None

        return str(value).strip() or None

    def _normalize_text(self, value: str) -> str:
        normalized: str = unicodedata.normalize("NFKD", value)
        normalized = "".join(character for character in normalized if not unicodedata.combining(character))
        normalized = normalized.lower()
        normalized = normalized.replace("%", " percent ")
        normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip()
