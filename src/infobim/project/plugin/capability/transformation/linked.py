import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from infobim.project.adapter.repository import ElementImportStepRepository
from infobim.project.domain.machine.import_state import ElementImportProcessState
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.context.adapter.repository import LocalContextFileResource
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class LinkedCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.infobim.project.plugin.capability.transformation.target.linked",
        version="1.0.0",
        name="Project element import transformation to Linked",
        description="Generate an ICDD linkset RDF linking workbook rows to instantiated IfcTask entities.",
        author=["TRAE"],
        tags=["project", "import", "linked", "icdd", "rdf"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return "Project element import transformation to Linked"

    def description(self, lang: str = "en") -> str:
        return "Generate an ICDD linkset RDF linking workbook rows to instantiated IfcTask entities."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        try:
            from rdflib import Graph, Literal, Namespace, URIRef
            from rdflib.namespace import DCTERMS, RDF, RDFS, XSD
        except ModuleNotFoundError as exc:
            raise ValueError("The 'rdflib' package is required to generate the ICDD linkset RDF.") from exc

        step_repository: Optional[ElementImportStepRepository] = context.get_parameter_value("element_import_step_repository")
        if not isinstance(step_repository, ElementImportStepRepository):
            step_repository = ElementImportStepRepository(
                container_path=str(context.get_parameter_value("container_path")),
                source_path=str(context.get_parameter_value("import_path")),
                element_name=str(context.get_parameter_value("element_name")),
            )
            context.set_parameter_value("element_import_step_repository", step_repository)

        generated_resource: LocalContextFileResource = step_repository.reload(ElementImportProcessState.GENERATED)
        generated_payload: Dict[str, Any] = json.loads(str(generated_resource.content))
        instantiated_resource: LocalContextFileResource = step_repository.reload(ElementImportProcessState.INSTANTIATED)
        instantiated_payload: Dict[str, Any] = json.loads(str(instantiated_resource.content))
        ifcjson_instances: List[Dict[str, Any]] = list(instantiated_payload.get("ifcjson_instances", []))
        if not ifcjson_instances:
            raise ValueError("The instantiated artifact does not expose any IfcTask payload to link.")

        container_path: Path = Path(str(context.get_parameter_value("container_path"))).expanduser().resolve()
        triple_dir: Path = container_path / "payload" / "triple"
        triple_dir.mkdir(parents=True, exist_ok=True)
        linkset_file_name: str = self._build_linkset_file_name(step_repository=step_repository)
        linkset_path: Path = triple_dir / linkset_file_name

        graph = Graph()
        CT = Namespace("https://standards.iso.org/iso/21597/-1/ed-1/en/Container#")
        LS = Namespace("https://standards.iso.org/iso/21597/-1/ed-1/en/Linkset#")
        graph.bind("ct", CT)
        graph.bind("ls", LS)
        graph.bind("dcterms", DCTERMS)
        graph.bind("rdf", RDF)
        graph.bind("rdfs", RDFS)

        container_uri = URIRef(f"urn:infobim:icdd:container:{step_repository.source_hash}")
        linkset_uri = URIRef(f"urn:infobim:icdd:linkset:{step_repository.source_hash}")
        workbook_uri = URIRef(f"urn:infobim:icdd:document:workbook:{step_repository.source_hash}")
        instantiated_uri = URIRef(f"urn:infobim:icdd:document:instantiated:{step_repository.source_hash}")

        graph.add((container_uri, RDF.type, CT.ContainerDescription))
        graph.add((container_uri, CT.name, Literal("InfoBIM ICDD Container", datatype=XSD.string)))
        graph.add((container_uri, CT.containsLinkset, linkset_uri))
        graph.add((container_uri, CT.containsDocument, workbook_uri))
        graph.add((container_uri, CT.containsDocument, instantiated_uri))

        graph.add((linkset_uri, RDF.type, CT.Linkset))
        graph.add((linkset_uri, CT.filename, Literal(self._to_container_relative_path(linkset_path, container_path), datatype=XSD.string)))
        graph.add((linkset_uri, DCTERMS.title, Literal("IfcWorkSchedule ICDD Linkset", lang="en")))

        workbook_path: Path = Path(str(generated_payload.get("workbook_path") or "")).expanduser().resolve()
        if not workbook_path.exists():
            raise FileNotFoundError(f"Generated workbook not found: {workbook_path}")
        graph.add((workbook_uri, RDF.type, CT.InternalDocument))
        graph.add((workbook_uri, CT.belongsToContainer, container_uri))
        graph.add((workbook_uri, CT.filename, Literal(self._to_container_relative_path(workbook_path, container_path), datatype=XSD.string)))
        graph.add((workbook_uri, CT.filetype, Literal("xlsx", datatype=XSD.string)))
        graph.add((workbook_uri, CT.name, Literal(workbook_path.name, datatype=XSD.string)))

        graph.add((instantiated_uri, RDF.type, CT.InternalDocument))
        graph.add((instantiated_uri, CT.belongsToContainer, container_uri))
        graph.add((instantiated_uri, CT.filename, Literal(self._to_container_relative_path(Path(instantiated_resource.path), container_path), datatype=XSD.string)))
        graph.add((instantiated_uri, CT.filetype, Literal("json", datatype=XSD.string)))
        graph.add((instantiated_uri, CT.name, Literal(Path(instantiated_resource.path).name, datatype=XSD.string)))

        link_count: int = 0
        for row_index, instance_payload in enumerate(ifcjson_instances, start=1):
            global_id: str = str(instance_payload.get("GlobalId") or "").strip()
            if not global_id:
                continue

            sanitized_global_id: str = re.sub(r"[^0-9A-Za-z_-]+", "_", global_id)
            from_element_uri = URIRef(f"urn:infobim:icdd:link-element:from:{step_repository.source_hash}:{sanitized_global_id}")
            to_element_uri = URIRef(f"urn:infobim:icdd:link-element:to:{step_repository.source_hash}:{sanitized_global_id}")
            from_identifier_uri = URIRef(f"urn:infobim:icdd:identifier:from:{step_repository.source_hash}:{sanitized_global_id}")
            to_identifier_uri = URIRef(f"urn:infobim:icdd:identifier:to:{step_repository.source_hash}:{sanitized_global_id}")
            link_uri = URIRef(f"urn:infobim:icdd:link:{step_repository.source_hash}:{sanitized_global_id}")

            graph.add((from_element_uri, RDF.type, LS.LinkElement))
            graph.add((from_element_uri, LS.hasDocument, workbook_uri))
            graph.add((from_element_uri, LS.hasIdentifier, from_identifier_uri))
            graph.add((from_identifier_uri, RDF.type, LS.StringBasedIdentifier))
            graph.add((from_identifier_uri, LS.identifier, Literal(global_id, datatype=XSD.string)))
            graph.add((from_identifier_uri, LS.identifierField, Literal("GlobalId", datatype=XSD.string)))

            graph.add((to_element_uri, RDF.type, LS.LinkElement))
            graph.add((to_element_uri, LS.hasDocument, instantiated_uri))
            graph.add((to_element_uri, LS.hasIdentifier, to_identifier_uri))
            graph.add((to_identifier_uri, RDF.type, LS.StringBasedIdentifier))
            graph.add((to_identifier_uri, LS.identifier, Literal(global_id, datatype=XSD.string)))
            graph.add((to_identifier_uri, LS.identifierField, Literal("GlobalId", datatype=XSD.string)))

            graph.add((link_uri, RDF.type, LS.DirectedBinaryLink))
            graph.add((link_uri, LS.hasFromLinkElement, from_element_uri))
            graph.add((link_uri, LS.hasToLinkElement, to_element_uri))
            graph.add((link_uri, RDFS.label, Literal(f"IfcTask link {row_index}", lang="en")))
            link_count += 1

        if link_count <= 0:
            raise ValueError("The ICDD linkset generator did not produce any link.")

        graph.serialize(destination=str(linkset_path), format="turtle")

        linked_payload: Dict[str, Any] = {
            "source_state": ElementImportProcessState.GENERATED.value,
            "source_artifact": str(generated_resource.path),
            "generated_workbook_path": str(workbook_path),
            "instantiated_artifact_path": str(instantiated_resource.path),
            "linkset_path": str(linkset_path),
            "summary": {
                "link_count": link_count,
                "ifc_task_count": len(ifcjson_instances),
            },
        }
        linked_artifact_path: Path = step_repository.write_text_file(
            state=ElementImportProcessState.LINKED,
            content=json.dumps(linked_payload, ensure_ascii=False, indent=2, sort_keys=True),
            file_type="json",
        )
        context.set_parameter_value("resource", LocalContextFileResource(linked_artifact_path))
        context.set_parameter_value("linkset_path", str(linkset_path))
        return {
            "resulting_state": ElementImportProcessState.LINKED,
            "path": str(linked_artifact_path),
            "linkset_path": str(linkset_path),
            "link_count": link_count,
        }

    def _build_linkset_file_name(self, step_repository: ElementImportStepRepository) -> str:
        element_name: str = re.sub(r"(?<!^)(?=[A-Z])", "_", step_repository.element_name).strip("_").lower()
        if not element_name:
            element_name = "element"
        return f"{element_name}_linkset_{step_repository.source_hash}.ttl"

    def _to_container_relative_path(self, path: Path, container_path: Path) -> str:
        return path.resolve().relative_to(container_path.resolve()).as_posix()
