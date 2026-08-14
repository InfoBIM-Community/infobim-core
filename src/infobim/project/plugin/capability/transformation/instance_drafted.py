import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from rdflib import Graph, URIRef
from rdflib.namespace import RDF, Namespace

from infobim.project.adapter.repository import ElementImportStepRepository
from infobim.project.domain.machine.import_state import ElementImportProcessState
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.context.adapter.repository import LocalContextFileResource
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class InstanceDraftedCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.infobim.project.plugin.capability.transformation.target.instance_drafted",
        version="1.0.0",
        name="Project element import transformation to Instance Drafted",
        description="Draft row-grouped IFC instances from the semanticized schedule headers and facade ontology.",
        author=["TRAE"],
        tags=["project", "import", "instance_drafted", "ifc", "facade"],
        supported_languages=["en", "pt-br"],
    )

    _FACADE = Namespace("http://datacenter.app.br/ontology/bsi/element/ifc_work_schedule/facade.ttl#")
    _SCHEMA = Namespace("https://schema.org/")

    def label(self, lang: str = "en") -> str:
        return "Project element import transformation to Instance Drafted"

    def description(self, lang: str = "en") -> str:
        return "Draft row-grouped IFC instances from the semanticized schedule headers and facade ontology."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        step_repository: Optional[ElementImportStepRepository] = context.get_parameter_value("element_import_step_repository")
        if not isinstance(step_repository, ElementImportStepRepository):
            step_repository = ElementImportStepRepository(
                container_path=str(context.get_parameter_value("container_path")),
                source_path=str(context.get_parameter_value("import_path")),
                element_name=str(context.get_parameter_value("element_name")),
            )
            context.set_parameter_value("element_import_step_repository", step_repository)

        semanticized_resource: LocalContextFileResource = step_repository.reload(ElementImportProcessState.SEMANTICIZED)
        grounded_resource: LocalContextFileResource = step_repository.reload(ElementImportProcessState.GROUNDED)
        semanticized_payload: Dict[str, Any] = json.loads(str(semanticized_resource.content))
        grounded_payload: Dict[str, Any] = json.loads(str(grounded_resource.content))

        semanticized_tables: List[Dict[str, Any]] = list(semanticized_payload.get("semanticized_tables", []))
        grounded_tables: List[Dict[str, Any]] = list(grounded_payload.get("grounded_tables", []))
        if not semanticized_tables:
            raise ValueError("The semanticized artifact does not contain semanticized tables.")
        if not grounded_tables:
            raise ValueError("The grounded artifact does not contain grounded tables.")

        facade_bundle: Dict[str, Any] = self._load_facade_bundle(root_path=str(context.root_path))
        row_groups: List[Dict[str, Any]] = self._build_row_groups(
            grounded_tables=grounded_tables,
            semanticized_tables=semanticized_tables,
            facade_field_index=dict(facade_bundle["facade_field_index"]),
        )

        instance_drafted_payload: Dict[str, Any] = {
            "source_state": ElementImportProcessState.SEMANTICIZED.value,
            "source_artifact": str(semanticized_resource.path),
            "facade_ontology_path": facade_bundle["ontology_path"],
            "summary": {
                "row_group_count": len(row_groups),
                "ifc_instance_count": sum(len(row_group.get("ifc_instances", [])) for row_group in row_groups),
                "mapped_field_count": sum(
                    len(instance.get("fields", []))
                    for row_group in row_groups
                    for instance in row_group.get("ifc_instances", [])
                ),
            },
            "row_groups": row_groups,
        }
        instance_drafted_path: Path = step_repository.write_text_file(
            state=ElementImportProcessState.INSTANCE_DRAFTED,
            content=json.dumps(instance_drafted_payload, ensure_ascii=True, indent=2, sort_keys=True),
            file_type="json",
        )
        context.set_parameter_value("resource", LocalContextFileResource(instance_drafted_path))
        return {
            "resulting_state": ElementImportProcessState.INSTANCE_DRAFTED,
            "path": str(instance_drafted_path),
            "row_group_count": len(row_groups),
        }

    def _build_row_groups(
        self,
        grounded_tables: Sequence[Dict[str, Any]],
        semanticized_tables: Sequence[Dict[str, Any]],
        facade_field_index: Dict[str, List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        semanticized_table_index: Dict[Tuple[int, int], Dict[str, Any]] = {
            (int(table.get("page_number", 0)), int(table.get("table_index", 0))): dict(table)
            for table in semanticized_tables
        }
        row_groups: List[Dict[str, Any]] = []
        for grounded_table in grounded_tables:
            table_key: Tuple[int, int] = (
                int(grounded_table.get("page_number", 0)),
                int(grounded_table.get("table_index", 0)),
            )
            semanticized_table: Optional[Dict[str, Any]] = semanticized_table_index.get(table_key)
            if semanticized_table is None:
                raise ValueError(
                    f"Missing semanticized table for grounded table page={table_key[0]} table={table_key[1]}.",
                )

            header_index: Dict[int, Dict[str, Any]] = {
                int(header.get("column_index", 0)): dict(header)
                for header in list(semanticized_table.get("headers", []))
            }
            for row in list(grounded_table.get("rows", [])):
                enriched_cells: List[Dict[str, Any]] = []
                for cell in list(row.get("cells", [])):
                    column_index: int = int(cell.get("column_index", 0))
                    semantic_header: Dict[str, Any] = dict(header_index.get(column_index, {}))
                    enriched_cells.append(
                        {
                            "column_index": column_index,
                            "header": cell.get("header"),
                            "text": cell.get("text"),
                            "text_normalized": cell.get("text_normalized"),
                            "bbox": cell.get("bbox", []),
                            "semantic_key": semantic_header.get("semantic_key"),
                            "header_field_uri": semantic_header.get("header_field_uri"),
                            "matched_term_kind": semantic_header.get("matched_term_kind"),
                            "matched_term_uri": semantic_header.get("matched_term_uri"),
                            "preferred_label": semantic_header.get("preferred_label"),
                            "preferred_label_uri": semantic_header.get("preferred_label_uri"),
                        }
                    )

                ifc_instances: List[Dict[str, Any]] = self._materialize_row_instances(
                    enriched_cells=enriched_cells,
                    facade_field_index=facade_field_index,
                )
                row_groups.append(
                    {
                        "page_number": grounded_table.get("page_number"),
                        "table_index": grounded_table.get("table_index"),
                        "global_table_index": grounded_table.get("global_table_index"),
                        "row_index": row.get("row_index"),
                        "row_reference": self._build_row_reference(enriched_cells=enriched_cells),
                        "ifc_instances": ifc_instances,
                    }
                )

        return row_groups

    def _materialize_row_instances(
        self,
        enriched_cells: Sequence[Dict[str, Any]],
        facade_field_index: Dict[str, List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        observations_by_role: Dict[str, List[Dict[str, Any]]] = {}
        facade_by_role: Dict[str, Dict[str, Any]] = {}
        for cell in enriched_cells:
            header_field_uri: str = str(cell.get("header_field_uri") or "").strip()
            if not header_field_uri:
                continue

            for facade_field in facade_field_index.get(header_field_uri, []):
                instance_role: str = str(facade_field["instance_role"])
                facade_by_role.setdefault(instance_role, dict(facade_field))
                observations_by_role.setdefault(instance_role, []).append(
                    {
                        **dict(facade_field),
                        "semantic_key": cell.get("semantic_key"),
                        "cell": dict(cell),
                        "values": self._split_cell_values(
                            value=str(cell.get("text") or ""),
                            multivalued=bool(facade_field["is_multivalued"]),
                        ),
                    }
                )

        ifc_instances: List[Dict[str, Any]] = []
        for instance_role, observations in observations_by_role.items():
            facade_payload: Dict[str, Any] = dict(facade_by_role[instance_role])
            is_repeatable: bool = bool(facade_payload["is_repeatable"])
            repeat_count: int = 1
            if is_repeatable:
                multivalued_observations: List[Dict[str, Any]] = [
                    observation
                    for observation in observations
                    if observation["is_multivalued"]
                ]
                if not multivalued_observations:
                    continue

                repeat_count = max(len(observation["values"]) for observation in multivalued_observations)
                if repeat_count <= 0:
                    continue

            for instance_index in range(1, repeat_count + 1):
                fields: List[Dict[str, Any]] = []
                for observation in observations:
                    raw_values: List[Dict[str, Any]] = list(observation["values"])
                    if not raw_values:
                        continue

                    if observation["is_multivalued"]:
                        value_payload: Dict[str, Any] = raw_values[min(instance_index - 1, len(raw_values) - 1)]
                    else:
                        value_payload = raw_values[0]

                    fields.append(
                        {
                            "field": observation["facade_field_identifier"],
                            "header_field_uri": observation["header_field_uri"],
                            "ifc_attribute_name": observation["ifc_attribute_name"],
                            "value": value_payload["value"],
                        }
                    )

                if not fields:
                    continue

                ifc_instances.append(
                    {
                        "instance_role": instance_role,
                        "instance_index": instance_index,
                        "ifc_class_name": facade_payload["ifc_class_name"],
                        "fields": fields,
                    }
                )

        return ifc_instances

    def _build_row_reference(self, enriched_cells: Sequence[Dict[str, Any]]) -> Dict[str, Optional[str]]:
        semantic_value_index: Dict[str, str] = {}
        for cell in enriched_cells:
            semantic_key: str = str(cell.get("semantic_key") or "").strip()
            value: str = str(cell.get("text") or "").strip()
            if semantic_key and value and semantic_key not in semantic_value_index:
                semantic_value_index[semantic_key] = value

        return {
            "identifier": semantic_value_index.get("identifier"),
            "work_breakdown_structure": semantic_value_index.get("work_breakdown_structure"),
            "task_name": semantic_value_index.get("task_name"),
        }

    def _load_facade_bundle(self, root_path: str) -> Dict[str, Any]:
        ontology_path: Path = (
            Path(root_path).expanduser().resolve()
            / "brasidatacenter"
            / "ontology"
            / "bsi"
            / "element"
            / "ifc_work_schedule"
            / "facade.ttl"
        )
        if not ontology_path.exists():
            raise FileNotFoundError(f"IfcWorkSchedule facade ontology not found: {ontology_path}")

        graph: Graph = Graph()
        graph.parse(str(ontology_path), format="turtle")
        facades: List[Dict[str, Any]] = []
        facade_field_index: Dict[str, List[Dict[str, Any]]] = {}
        for facade_uri in graph.subjects(RDF.type, self._FACADE.DataEntityFacade):
            facade_payload: Dict[str, Any] = {
                "facade_uri": str(facade_uri),
                "facade_identifier": self._graph_literal(graph, facade_uri, self._SCHEMA.identifier),
                "facade_name": self._graph_literal(graph, facade_uri, self._SCHEMA.name),
                "ifc_class_name": self._graph_literal(graph, facade_uri, self._FACADE.ifcClassName),
                "instance_role": self._graph_literal(graph, facade_uri, self._FACADE.instanceRole),
                "is_repeatable": self._graph_boolean(graph, facade_uri, self._FACADE.isRepeatable),
                "fields": [],
            }
            if not facade_payload["facade_identifier"]:
                raise ValueError(f"Facade identifier is missing: {facade_uri}")
            if not facade_payload["ifc_class_name"]:
                raise ValueError(f"Facade IFC class name is missing: {facade_uri}")
            if not facade_payload["instance_role"]:
                raise ValueError(f"Facade instance role is missing: {facade_uri}")

            for field_uri in graph.objects(facade_uri, self._FACADE.hasFacadeField):
                header_field_uri: Optional[URIRef] = graph.value(field_uri, self._FACADE.mapsFromHeaderField)
                if header_field_uri is None:
                    raise ValueError(f"Facade field does not map from any HeaderField: {field_uri}")

                field_payload: Dict[str, Any] = {
                    "facade_field_uri": str(field_uri),
                    "facade_field_identifier": self._graph_literal(graph, field_uri, self._SCHEMA.identifier),
                    "facade_field_name": self._graph_literal(graph, field_uri, self._SCHEMA.name),
                    "header_field_uri": str(header_field_uri),
                    "ifc_attribute_name": self._graph_literal(graph, field_uri, self._FACADE.ifcAttributeName),
                    "maps_to_property_uri": self._graph_uri(graph, field_uri, self._FACADE.mapsToProperty),
                    "is_multivalued": self._graph_boolean(graph, field_uri, self._FACADE.isMultivalued),
                    "is_required": self._graph_boolean(graph, field_uri, self._FACADE.isRequired),
                    "field_datatype_uri": self._graph_uri(graph, field_uri, self._FACADE.fieldDatatype),
                    "facade_uri": facade_payload["facade_uri"],
                    "facade_identifier": facade_payload["facade_identifier"],
                    "ifc_class_name": facade_payload["ifc_class_name"],
                    "instance_role": facade_payload["instance_role"],
                    "is_repeatable": facade_payload["is_repeatable"],
                    "semantic_key": None,
                }
                if not field_payload["facade_field_identifier"]:
                    raise ValueError(f"Facade field identifier is missing: {field_uri}")

                facade_payload["fields"].append(
                    {
                        "uri": field_payload["facade_field_uri"],
                        "identifier": field_payload["facade_field_identifier"],
                        "name": field_payload["facade_field_name"],
                        "header_field_uri": field_payload["header_field_uri"],
                        "ifc_attribute_name": field_payload["ifc_attribute_name"],
                        "is_multivalued": field_payload["is_multivalued"],
                    }
                )
                facade_field_index.setdefault(field_payload["header_field_uri"], []).append(field_payload)

            facades.append(facade_payload)

        if not facades:
            raise ValueError(f"No facades were loaded from ontology: {ontology_path}")

        return {
            "ontology_path": str(ontology_path),
            "facades": facades,
            "facade_field_index": facade_field_index,
        }

    def _split_cell_values(self, value: str, multivalued: bool) -> List[Dict[str, str]]:
        stripped_value: str = value.strip()
        if not stripped_value:
            return []

        if not multivalued:
            return [
                {
                    "value": stripped_value,
                    "value_normalized": stripped_value.casefold(),
                }
            ]

        raw_tokens: List[str] = [
            token.strip()
            for token in re.split(r"[,\n;]+", stripped_value)
            if token.strip()
        ]
        if not raw_tokens:
            return []

        return [
            {
                "value": token,
                "value_normalized": token.casefold(),
            }
            for token in raw_tokens
        ]

    def _graph_literal(self, graph: Graph, subject: URIRef, predicate: URIRef) -> Optional[str]:
        value = graph.value(subject, predicate)
        if value is None:
            return None

        return str(value).strip() or None

    def _graph_uri(self, graph: Graph, subject: URIRef, predicate: URIRef) -> Optional[str]:
        value = graph.value(subject, predicate)
        if value is None:
            return None

        return str(value).strip() or None

    def _graph_boolean(self, graph: Graph, subject: URIRef, predicate: URIRef) -> bool:
        value = graph.value(subject, predicate)
        if value is None:
            return False

        normalized_value: str = str(value).strip().lower()
        return normalized_value in {"1", "true"}
