"""Write an ISO 21597 linkset declaring an IFCX as a version of its source DXF."""

from typing import ClassVar
from pathlib import Path

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, RDF

from infobim.project.domain.model.contract import ProjectContract
from infobim.drawing.adapter.transformation_payload import TransformationPayloadPath


class DxfIfcxLinksetWriter:
    """Persist a DXF -> IFCX conversion as an ISO 21597 Identity linkset.

    Same shape as DwgDxfLinksetWriter, one step later in the pipeline: the
    DXF and IFCX are each declared as a ct:ExternalDocument, connected by an
    ls:Link typed els:Identity, plus dcterms:isVersionOf / hasVersion for a
    directly queryable version relationship.
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
    def write(cls, container: Path, dxf_path: Path, ifcx_path: Path) -> Path:
        dxf_hash: str = TransformationPayloadPath.identifier_for(dxf_path)
        destination: Path = (
            container
            / ProjectContract.DATASET_NAME
            / "payload"
            / cls.LINKSET_DIRECTORY_NAME
            / f"{dxf_hash}.ttl"
        )
        if destination.is_file():
            return destination

        graph: Graph = cls.graph_for(dxf_hash, dxf_path, ifcx_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(graph.serialize(format="turtle", encoding="utf-8"))

        return destination

    @classmethod
    def graph_for(cls, dxf_hash: str, dxf_path: Path, ifcx_path: Path) -> Graph:
        """
        Build the linkset graph without writing it.

        Public so a caller that also needs a different serialization of the
        same linkset (DxfIfcxLinksetCapability writes it again as JSON-LD,
        for its ETL state event) does not reconstruct these triples by hand.
        """
        dxf_document: URIRef = URIRef(f"{cls.DOCUMENT_URI_PREFIX}dxf/{dxf_hash}")
        ifcx_document: URIRef = URIRef(f"{cls.DOCUMENT_URI_PREFIX}ifcx/{dxf_hash}")
        link: URIRef = URIRef(f"{cls.LINK_URI_PREFIX}{dxf_hash}")
        from_element: URIRef = URIRef(f"{link}/from")
        to_element: URIRef = URIRef(f"{link}/to")

        graph: Graph = Graph()
        graph.bind("ct", cls.CONTAINER_NAMESPACE)
        graph.bind("ls", cls.LINKSET_NAMESPACE)
        graph.bind("els", cls.EXTENDED_LINKSET_NAMESPACE)
        graph.bind("dcterms", DCTERMS)

        graph.add((dxf_document, RDF.type, cls.CONTAINER_NAMESPACE.ExternalDocument))
        graph.add((dxf_document, cls.CONTAINER_NAMESPACE.hasIdentifier, Literal(dxf_hash)))
        graph.add((dxf_document, cls.CONTAINER_NAMESPACE.filename, Literal(dxf_path.name)))
        graph.add((dxf_document, DCTERMS.hasVersion, ifcx_document))

        graph.add((ifcx_document, RDF.type, cls.CONTAINER_NAMESPACE.ExternalDocument))
        graph.add((ifcx_document, cls.CONTAINER_NAMESPACE.hasIdentifier, Literal(dxf_hash)))
        graph.add((ifcx_document, cls.CONTAINER_NAMESPACE.filename, Literal(ifcx_path.name)))
        graph.add((ifcx_document, DCTERMS.isVersionOf, dxf_document))

        graph.add((from_element, RDF.type, cls.LINKSET_NAMESPACE.LinkElement))
        graph.add((from_element, cls.LINKSET_NAMESPACE.hasDocument, ifcx_document))
        graph.add((to_element, RDF.type, cls.LINKSET_NAMESPACE.LinkElement))
        graph.add((to_element, cls.LINKSET_NAMESPACE.hasDocument, dxf_document))

        graph.add((link, RDF.type, cls.LINKSET_NAMESPACE.Link))
        graph.add((link, RDF.type, cls.EXTENDED_LINKSET_NAMESPACE.Identity))
        graph.add((link, cls.LINKSET_NAMESPACE.hasFromLinkElement, from_element))
        graph.add((link, cls.LINKSET_NAMESPACE.hasToLinkElement, to_element))

        return graph
