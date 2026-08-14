from pathlib import Path
import json
from datetime import datetime, timezone
from typing import Any, Dict

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD

from ontobdc.context.plugin.check.has_valid_context.check import main as check_valid_context
from ontobdc.context.plugin.check.has_valid_context.hotfix import main as hotfix_valid_context


class IfcRuntimeEntityAdapter:
    _BASE_CONTEXT_URI: Namespace = Namespace("urn:ontobdc:context/")
    _INFOBIM_ENTITY_URI: Namespace = Namespace("urn:infobim:context/entity/")
    _IFCOWL: Namespace = Namespace("http://ifcowl.openbimstandards.org/IFC4#")

    def resolve(self, raw_element: str) -> Dict[str, str]:
        normalized_name: str = self._normalize_element_name(raw_element)
        if not normalized_name:
            raise ValueError(f"Invalid IFC element name: {raw_element}")

        if not normalized_name.startswith("Ifc"):
            raise ValueError(f"Invalid IFC element name: {raw_element}")

        return {
            "element_name": normalized_name,
            "element_uri": str(self._IFCOWL[normalized_name]),
            "entity_uri": str(self._INFOBIM_ENTITY_URI[normalized_name]),
        }

    def register(self, root_path: str, raw_element: str) -> Dict[str, str]:
        resolved: Dict[str, str] = self.resolve(raw_element)
        if check_valid_context(root_path=root_path) != 0 and hotfix_valid_context(root_path=root_path) != 0:
            raise ValueError("Could not initialize context.ttl for InfoBIM context entity registration.")

        context_file: Path = Path(root_path).expanduser().resolve() / ".__ontobdc__" / "context.ttl"
        graph: Graph = Graph()
        graph.parse(str(context_file), format="turtle")
        graph.bind("", self._BASE_CONTEXT_URI)
        graph.bind("owl", OWL)
        graph.bind("rdfs", RDFS)
        graph.bind("ifcowl", self._IFCOWL)
        graph.bind("infobimctx", self._INFOBIM_ENTITY_URI)

        entity_ref: URIRef = URIRef(resolved["entity_uri"])
        ifc_element_ref: URIRef = URIRef(resolved["element_uri"])
        runtime_entity_type: URIRef = self._BASE_CONTEXT_URI["RuntimeIfcEntity"]
        references_ifc_element: URIRef = self._BASE_CONTEXT_URI["referencesIfcElement"]
        entity_name_predicate: URIRef = self._BASE_CONTEXT_URI["entityName"]

        graph.add((entity_ref, RDF.type, OWL.Class))
        graph.add((entity_ref, RDF.type, runtime_entity_type))
        graph.add((entity_ref, RDFS.label, Literal(resolved["element_name"])))
        graph.add((entity_ref, entity_name_predicate, Literal(resolved["element_name"])))
        graph.add((entity_ref, references_ifc_element, ifc_element_ref))
        graph.add((entity_ref, RDFS.seeAlso, ifc_element_ref))
        graph.serialize(destination=context_file, format="turtle")

        resolved["context_file"] = str(context_file)
        return resolved

    def persist_learning_record(self, root_path: str, published_payload: Dict[str, Any]) -> str:
        if check_valid_context(root_path=root_path) != 0 and hotfix_valid_context(root_path=root_path) != 0:
            raise ValueError("Could not initialize context.ttl for InfoBIM learning record persistence.")

        context_file: Path = Path(root_path).expanduser().resolve() / ".__ontobdc__" / "context.ttl"
        graph: Graph = Graph()
        graph.parse(str(context_file), format="turtle")
        graph.bind("", self._BASE_CONTEXT_URI)
        graph.bind("owl", OWL)
        graph.bind("rdfs", RDFS)
        graph.bind("xsd", XSD)
        graph.bind("ifcowl", self._IFCOWL)
        graph.bind("infobimctx", self._INFOBIM_ENTITY_URI)

        context_ref: URIRef = self._BASE_CONTEXT_URI["CurrentContext"]
        record_ref: URIRef = URIRef(str(published_payload["record_uri"]).strip())
        record_type: URIRef = self._BASE_CONTEXT_URI["EntityLearningRecord"]
        has_record_predicate: URIRef = self._BASE_CONTEXT_URI["hasEntityLearningRecord"]
        entity_uri_predicate: URIRef = self._BASE_CONTEXT_URI["entityUri"]
        source_file_predicate: URIRef = self._BASE_CONTEXT_URI["sourceFile"]
        source_file_path_predicate: URIRef = self._BASE_CONTEXT_URI["sourceFilePath"]
        supported_file_type_predicate: URIRef = self._BASE_CONTEXT_URI["supportedFileType"]
        content_language_predicate: URIRef = self._BASE_CONTEXT_URI["contentLanguage"]
        language_score_predicate: URIRef = self._BASE_CONTEXT_URI["languageScore"]
        aligned_vector_predicate: URIRef = self._BASE_CONTEXT_URI["alignedVector"]
        learned_at_predicate: URIRef = self._BASE_CONTEXT_URI["learnedAt"]

        entity_ref: URIRef = URIRef(str(published_payload["entity_uri"]).strip())
        source_file_path: Path = Path(str(published_payload["source_file"]).strip()).expanduser().resolve()
        supported_file_type: str = str(published_payload.get("supported_file_type", "")).strip()
        language_payload: Dict[str, Any] = dict(published_payload.get("language", {}))
        weight_payload: Any = published_payload.get("weight", [])

        graph.remove((record_ref, None, None))
        graph.add((context_ref, has_record_predicate, record_ref))
        graph.add((record_ref, RDF.type, OWL.NamedIndividual))
        graph.add((record_ref, RDF.type, record_type))
        graph.add((record_ref, entity_uri_predicate, entity_ref))
        graph.add((record_ref, source_file_predicate, URIRef(source_file_path.as_uri())))
        graph.add((record_ref, source_file_path_predicate, Literal(str(source_file_path))))
        graph.add((record_ref, supported_file_type_predicate, Literal(supported_file_type)))
        graph.add((record_ref, content_language_predicate, Literal(str(language_payload.get("code", "")).strip())))
        graph.add(
            (
                record_ref,
                language_score_predicate,
                Literal(float(language_payload.get("score", 0.0)), datatype=XSD.decimal),
            )
        )
        graph.add((record_ref, aligned_vector_predicate, Literal(json.dumps(weight_payload, ensure_ascii=True))))
        graph.add(
            (
                record_ref,
                learned_at_predicate,
                Literal(datetime.now(timezone.utc).replace(microsecond=0).isoformat(), datatype=XSD.dateTime),
            )
        )
        graph.add((entity_ref, supported_file_type_predicate, Literal(supported_file_type)))
        graph.serialize(destination=context_file, format="turtle")
        return str(context_file)

    def _normalize_element_name(self, raw_element: str) -> str:
        candidate: str = str(raw_element).strip()
        if not candidate:
            return ""

        if "#" in candidate:
            candidate = candidate.rsplit("#", 1)[-1]
        elif "/" in candidate:
            candidate = candidate.rstrip("/").rsplit("/", 1)[-1]

        candidate = "".join(character for character in candidate if character.isalnum() or character == "_")
        if not candidate:
            return ""

        if candidate.lower().startswith("ifc"):
            suffix: str = candidate[3:]
            if not suffix:
                return "Ifc"
            return f"Ifc{suffix[:1].upper()}{suffix[1:]}"

        return f"Ifc{candidate[:1].upper()}{candidate[1:]}"
