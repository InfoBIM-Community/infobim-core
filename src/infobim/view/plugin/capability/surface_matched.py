from __future__ import annotations

from typing import Any, Dict, List

from rdflib import Graph, URIRef
from rdflib.namespace import RDF

from infobim.project.domain.model.contract import IFCOWL_NS
from infobim.view.adapter.component import InfoBIMComponentLoader
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.storage.adapter.bootstrap import StorageNamespaceBootstrap
from ontobdc.view.plugin.capability.transformation.surface_matched import (
    FILE_SIZE_TILE_CLASS_URI,
    SurfaceMatchedCapability,
)


StorageNamespaceBootstrap.initialize()
_OBDC = StorageNamespaceBootstrap.OBDC


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
        project_resource = str(
            context.get_parameter_value("infobim_project_resource") or ""
        )
        # Keep the projection/component available to explicit consumers, but
        # do not place Distributed IFC on the default InfoBIM Surface.
        ifc_model_resource = str(
            context.get_parameter_value("infobim_ifc_model_resource") or ""
        )
        requests: List[Dict[str, Any]] = []
        seen = set()
        if project_resource and URIRef(project_resource) in set(graph.subjects()):
            requests.append({"data": project_resource, "region": "content"})
            seen.add(project_resource)

        requests.append(
            {"tileClass": FILE_SIZE_TILE_CLASS_URI, "region": "content"}
        )

        for request in super()._auto_matched_requests(graph):
            resource = str(request.get("data") or "")
            if not resource or resource in seen or resource == ifc_model_resource:
                continue
            subject = URIRef(resource)
            types = {
                value
                for value in graph.objects(subject, RDF.type)
                if isinstance(value, URIRef)
            }
            if _OBDC.DataContainer in types:
                continue
            if any(str(value).startswith(IFCOWL_NS) for value in types):
                continue
            requests.append(request)
            seen.add(resource)
        return requests
