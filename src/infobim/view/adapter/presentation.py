from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, RDF

from infobim.project.domain.model.contract import (
    IFCOWL_NS,
    IFC_PROJECT_FIELDS,
)
from infobim.view.domain.model import InfoBIMProjectPresentation
from ontobdc.storage.adapter.bootstrap import OBDC


SCHEMA = "https://schema.org/"
IFC_MODEL_MEDIA_TYPE = "application/vnd.infobim.ifc-model+json"


class InfoBIMPresentationContextAdapter:
    """Add an ephemeral BIM projection to DATA_GATHERED JSON-LD.

    The source datasets remain untouched. The extra model node belongs only
    to the presentation ETL state consumed by the generic OntoBDC pipeline.
    """

    def augment(
        self,
        gathered_path: Path,
        presentation: InfoBIMProjectPresentation,
    ) -> str:
        graph = Graph()
        graph.parse(str(gathered_path), format="json-ld")

        project_subject = URIRef(presentation.project_subject)
        graph.set(
            (project_subject, DCTERMS.identifier, Literal(presentation.project_id))
        )
        project_name = str(
            presentation.project.get("Name")
            or presentation.project.get("name")
            or presentation.project_id
        ).strip()
        graph.set((project_subject, DCTERMS.title, Literal(project_name)))

        for field_name, property_name in IFC_PROJECT_FIELDS:
            value = presentation.project.get(field_name)
            if value is None or not str(value).strip():
                continue
            graph.set(
                (
                    project_subject,
                    URIRef(f"{IFCOWL_NS}{property_name}"),
                    Literal(value),
                )
            )

        model_subject = URIRef(
            "urn:infobim:presentation:ifc-model:"
            + quote(presentation.project_id, safe="")
        )
        graph.add((model_subject, RDF.type, OBDC.DataEntity))
        graph.set((model_subject, DCTERMS.title, Literal("IFC Model")))
        graph.set(
            (model_subject, DCTERMS.identifier, Literal(presentation.project_id))
        )
        graph.set(
            (
                model_subject,
                URIRef(f"{SCHEMA}encodingFormat"),
                Literal(IFC_MODEL_MEDIA_TYPE),
            )
        )
        graph.set(
            (
                model_subject,
                RDF.value,
                Literal(
                    json.dumps(
                        presentation.model_payload(),
                        ensure_ascii=False,
                        separators=(",", ":"),
                        default=str,
                    )
                ),
            )
        )

        graph.serialize(
            destination=str(gathered_path),
            format="json-ld",
            indent=2,
        )
        return str(model_subject)

