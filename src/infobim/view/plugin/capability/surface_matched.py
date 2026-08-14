from __future__ import annotations

from typing import Any, Dict, List

from rdflib import Graph, URIRef
from rdflib.namespace import RDF

from infobim.project.domain.model.contract import IFCOWL_NS
from infobim.view.adapter.component import InfoBIMComponentLoader
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.storage.adapter.bootstrap import OBDC
from ontobdc.view.plugin.capability.transformation.surface_matched import (
    SurfaceMatchedCapability,
)


class InfoBIMSurfaceMatchedCapability(SurfaceMatchedCapability):
    """Match one BIM model domain while retaining generic OntoBDC entities."""

    def __init__(self) -> None:
        super().__init__()
        self._components = InfoBIMComponentLoader()

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        graph = self._gathered_graph(context)
        context.set_parameter_value(
            "surface_matches",
            self._project_requests(graph, context),
        )
        return super().execute(context)

    def _project_requests(
        self,
        graph: Graph,
        context: CliContextPort,
    ) -> List[Dict[str, Any]]:
        requested_resources = [
            str(context.get_parameter_value("infobim_project_resource") or ""),
            str(context.get_parameter_value("infobim_ifc_model_resource") or ""),
        ]
        requests: List[Dict[str, Any]] = []
        seen = set()
        for resource in requested_resources:
            if resource and URIRef(resource) in set(graph.subjects()):
                requests.append({"data": resource, "region": "content"})
                seen.add(resource)

        for request in super()._auto_matched_requests(graph):
            resource = str(request.get("data") or "")
            if not resource or resource in seen:
                continue
            subject = URIRef(resource)
            types = {
                value
                for value in graph.objects(subject, RDF.type)
                if isinstance(value, URIRef)
            }
            if OBDC.DataContainer in types:
                continue
            if any(str(value).startswith(IFCOWL_NS) for value in types):
                continue
            requests.append(request)
            seen.add(resource)
        return requests

