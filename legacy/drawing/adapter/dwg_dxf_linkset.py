"""Write an ISO 21597 linkset declaring a DXF as a version of its source DWG."""

from typing import ClassVar
from pathlib import Path

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, RDF

from infobim.project.domain.model.contract import ProjectContract
from infobim.drawing.adapter.transformation_payload import TransformationPayloadPath


class DwgDxfLinksetWriter:
    """Persist a DWG -> DXF conversion as an ISO 21597 Identity linkset.

    The DWG and DXF are each declared as a ct:ExternalDocument, connected by
    an ls:Link typed els:Identity (same document, converted representation),
    plus dcterms:isVersionOf / dcterms:hasVersion for a directly queryable
    version relationship alongside the ICDD-conformant structure.
    """

    LINKSET_DIRECTORY_NAME: ClassVar[str] = "linkset"

    DOCUMENT_URI_PREFIX: ClassVar[str] = "urn:infobim:document/"
    LINK_URI_PREFIX: ClassVar[str] = "urn:infobim:link/"

    CONTAINER_NAMESPACE: ClassVar[Namespace] = Namespace(
        "https://standards.iso.org/iso/21597/-1/ed-1/en/Container#"
    )
    LINKSET_NAMESPACE: ClassVar[Namespace] = Namespace(
        "https://standards.iso.org/iso/21597/-1/ed-1/en/Linkset#"
    )
    EXTENDED_LINKSET_NAMESPACE: ClassVar[Namespace] = Namespace(
        "https://standards.iso.org/iso/21597/-2/ed-1/en/ExtendedLinkset#"
    )

    @classmethod
    def write(cls, container: Path, dwg_path: Path, dxf_path: Path) -> Path:
        dwg_hash: str = TransformationPayloadPath.identifier_for(dwg_path)
        destination: Path = (
            container
            / ProjectContract.DATASET_NAME
            / "payload"
            / cls.LINKSET_DIRECTORY_NAME
            / f"{dwg_hash}.ttl"
        )
        if destination.is_file():
            return destination

        graph: Graph = cls.graph_for(dwg_hash, dwg_path, dxf_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(graph.serialize(format="turtle", encoding="utf-8"))

        return destination

    @classmethod
    def graph_for(cls, dwg_hash: str, dwg_path: Path, dxf_path: Path) -> Graph:
        """
        Build the linkset graph without writing it.

        Public so a caller that also needs a different serialization of the
        same linkset (DwgDxfLinksetCapability writes it again as JSON-LD, for
        its ETL state event) does not reconstruct these triples by hand.
        """
        dwg_document: URIRef = URIRef(f"{cls.DOCUMENT_URI_PREFIX}dwg/{dwg_hash}")
        dxf_document: URIRef = URIRef(f"{cls.DOCUMENT_URI_PREFIX}dxf/{dwg_hash}")
        link: URIRef = URIRef(f"{cls.LINK_URI_PREFIX}{dwg_hash}")
        from_element: URIRef = URIRef(f"{link}/from")
        to_element: URIRef = URIRef(f"{link}/to")

        graph: Graph = Graph()
        graph.bind("ct", cls.CONTAINER_NAMESPACE)
        graph.bind("ls", cls.LINKSET_NAMESPACE)
        graph.bind("els", cls.EXTENDED_LINKSET_NAMESPACE)
        graph.bind("dcterms", DCTERMS)

        graph.add((dwg_document, RDF.type, cls.CONTAINER_NAMESPACE.ExternalDocument))
        graph.add((dwg_document, cls.CONTAINER_NAMESPACE.hasIdentifier, Literal(dwg_hash)))
        graph.add((dwg_document, cls.CONTAINER_NAMESPACE.filename, Literal(dwg_path.name)))
        graph.add((dwg_document, DCTERMS.hasVersion, dxf_document))

        graph.add((dxf_document, RDF.type, cls.CONTAINER_NAMESPACE.ExternalDocument))
        graph.add((dxf_document, cls.CONTAINER_NAMESPACE.hasIdentifier, Literal(dwg_hash)))
        graph.add((dxf_document, cls.CONTAINER_NAMESPACE.filename, Literal(dxf_path.name)))
        graph.add((dxf_document, DCTERMS.isVersionOf, dwg_document))

        graph.add((from_element, RDF.type, cls.LINKSET_NAMESPACE.LinkElement))
        graph.add((from_element, cls.LINKSET_NAMESPACE.hasDocument, dxf_document))
        graph.add((to_element, RDF.type, cls.LINKSET_NAMESPACE.LinkElement))
        graph.add((to_element, cls.LINKSET_NAMESPACE.hasDocument, dwg_document))

        graph.add((link, RDF.type, cls.LINKSET_NAMESPACE.Link))
        graph.add((link, RDF.type, cls.EXTENDED_LINKSET_NAMESPACE.Identity))
        graph.add((link, cls.LINKSET_NAMESPACE.hasFromLinkElement, from_element))
        graph.add((link, cls.LINKSET_NAMESPACE.hasToLinkElement, to_element))

        return graph
