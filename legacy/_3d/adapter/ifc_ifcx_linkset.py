"""Write the ISO 21597 linkset of an element's IFCX mesh and its IFC model."""

from typing import ClassVar
from pathlib import Path

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, RDF

from infobim.project.domain.model.contract import ProjectContract


class IfcIfcxLinksetWriter:
    """Persist an IFC element's mesh conversion as an ISO 21597 linkset.

    Same shape as DxfIfcxLinksetWriter, for the other source format: the
    IFC model and the IFCX mesh of one of its elements are each declared
    as a ct:ExternalDocument, connected by an ls:Link typed els:Identity,
    plus dcterms:isVersionOf / hasVersion for a directly queryable
    version relationship.

    The mesh document carries the element's own identity — it is modelled
    as an ifcOWL IfcDocumentInformation with globalId_IfcRoot and
    name_IfcRoot — because an element, unlike a drawing, arrives with a
    GlobalId of its own and nothing has to invent one for it. That is
    also what lets anything downstream go from a mesh file back to the
    element it draws.
    """

    LINKSET_DIRECTORY_NAME: ClassVar[str] = "linkset"

    DOCUMENT_URI_PREFIX: ClassVar[str] = "urn:infobim:document/"
    LINK_URI_PREFIX: ClassVar[str] = "urn:infobim:link/"

    IFCOWL_PREFIX: ClassVar[str] = "ifc4x3"
    DOCUMENT_INFORMATION_LOCAL_NAME: ClassVar[str] = "IfcDocumentInformation"
    GLOBAL_ID_LOCAL_NAME: ClassVar[str] = "globalId_IfcRoot"
    NAME_LOCAL_NAME: ClassVar[str] = "name_IfcRoot"

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
    def write(
        cls,
        container: Path,
        model_path: Path,
        ifcx_path: Path,
        global_id: str,
        name: str,
    ) -> Path:
        """
        Write the linkset of one element's mesh and return where it went.

        The file is named after the element, as the mesh itself is, so
        whoever holds one holds the name of the other.
        """
        destination: Path = (
            container
            / ProjectContract.DATASET_NAME
            / ProjectContract.PAYLOAD_DIRECTORY_NAME
            / cls.LINKSET_DIRECTORY_NAME
            / f"{global_id}.ttl"
        )
        graph: Graph = cls.graph_for(model_path, ifcx_path, global_id, name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(graph.serialize(format="turtle", encoding="utf-8"))

        return destination

    @classmethod
    def graph_for(
        cls,
        model_path: Path,
        ifcx_path: Path,
        global_id: str,
        name: str,
    ) -> Graph:
        """
        Build the linkset graph without writing it.
        """
        ifcowl: Namespace = Namespace(ProjectContract.IFCOWL_NAMESPACE)
        ifc_document: URIRef = URIRef(f"{cls.DOCUMENT_URI_PREFIX}ifc/{global_id}")
        ifcx_document: URIRef = URIRef(f"{cls.DOCUMENT_URI_PREFIX}ifcx/{global_id}")
        link: URIRef = URIRef(f"{cls.LINK_URI_PREFIX}{global_id}")
        from_element: URIRef = URIRef(f"{link}/from")
        to_element: URIRef = URIRef(f"{link}/to")

        graph: Graph = Graph()
        graph.bind("ct", cls.CONTAINER_NAMESPACE)
        graph.bind("ls", cls.LINKSET_NAMESPACE)
        graph.bind("els", cls.EXTENDED_LINKSET_NAMESPACE)
        graph.bind("dcterms", DCTERMS)
        graph.bind(cls.IFCOWL_PREFIX, ifcowl)

        graph.add((ifc_document, RDF.type, cls.CONTAINER_NAMESPACE.ExternalDocument))
        graph.add((
            ifc_document,
            cls.CONTAINER_NAMESPACE.hasIdentifier,
            Literal(global_id),
        ))
        graph.add((
            ifc_document,
            cls.CONTAINER_NAMESPACE.filename,
            Literal(model_path.name),
        ))
        graph.add((ifc_document, DCTERMS.hasVersion, ifcx_document))

        graph.add((ifcx_document, RDF.type, cls.CONTAINER_NAMESPACE.ExternalDocument))
        graph.add((
            ifcx_document,
            RDF.type,
            ifcowl[cls.DOCUMENT_INFORMATION_LOCAL_NAME],
        ))
        graph.add((
            ifcx_document,
            cls.CONTAINER_NAMESPACE.hasIdentifier,
            Literal(global_id),
        ))
        graph.add((
            ifcx_document,
            cls.CONTAINER_NAMESPACE.filename,
            Literal(ifcx_path.name),
        ))
        graph.add((ifcx_document, ifcowl[cls.GLOBAL_ID_LOCAL_NAME], Literal(global_id)))
        graph.add((ifcx_document, ifcowl[cls.NAME_LOCAL_NAME], Literal(name)))
        graph.add((ifcx_document, DCTERMS.isVersionOf, ifc_document))

        graph.add((from_element, RDF.type, cls.LINKSET_NAMESPACE.LinkElement))
        graph.add((from_element, cls.LINKSET_NAMESPACE.hasDocument, ifcx_document))
        graph.add((to_element, RDF.type, cls.LINKSET_NAMESPACE.LinkElement))
        graph.add((to_element, cls.LINKSET_NAMESPACE.hasDocument, ifc_document))

        graph.add((link, RDF.type, cls.LINKSET_NAMESPACE.Link))
        graph.add((link, RDF.type, cls.EXTENDED_LINKSET_NAMESPACE.Identity))
        graph.add((link, cls.LINKSET_NAMESPACE.hasFromLinkElement, from_element))
        graph.add((link, cls.LINKSET_NAMESPACE.hasToLinkElement, to_element))

        return graph
