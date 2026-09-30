from typing import ClassVar, List, Optional, Set
from pathlib import Path

from rdflib import Graph, URIRef
from rdflib.namespace import RDF

from infobim.ifc.domain.port.schema import IfcProjectSchemaResolverPort
from infobim.ifc.adapter.vocabulary import IfcSchemaVocabulary
from infobim.project.domain.model.contract import ProjectContract
from infobim.ifc.domain.exception.conversion import (
    IfcProjectSchemaNotResolvedError,
)


class IfcProjectGraph:
    """
    Reads the IfcProject a project declares, from the one file that holds it.

    The declaration lives in ``.__infobim__/payload/triple/ifc_project.ttl``
    and nowhere else, so reading it is a single operation the IFC runtime
    owns: open that file, and answer which subject is the IfcProject and how
    it is typed. Nothing here falls back to another file, another property
    or another representation.
    """

    TRIPLE_FORMAT: ClassVar[str] = "turtle"

    @classmethod
    def path_of(cls, project_path: Path) -> Path:
        """
        Return where the project declares its IfcProject.
        """
        return project_path.joinpath(
            ProjectContract.DATASET_NAME,
            ProjectContract.PAYLOAD_DIRECTORY_NAME,
            ProjectContract.TRIPLE_DIRECTORY_NAME,
            ProjectContract.IFC_PROJECT_FILE_NAME,
        )

    @classmethod
    def load(cls, declaration_path: Path) -> Graph:
        """
        Return the declared graph, or fail saying which file is unreadable.
        """
        graph: Graph = Graph()
        try:
            graph.parse(str(declaration_path), format=cls.TRIPLE_FORMAT)
        except Exception as error:
            raise IfcProjectSchemaNotResolvedError(
                f"The IfcProject declaration is unreadable: "
                f"{declaration_path} ({error})."
            ) from error

        return graph

    @classmethod
    def subjects_of(cls, graph: Graph) -> List[URIRef]:
        """
        Return every subject the graph types as an IfcProject.
        """
        subjects: List[URIRef] = []
        subject: URIRef
        class_uri: URIRef
        for subject, class_uri in graph.subject_objects(RDF.type):
            if not isinstance(subject, URIRef) or not isinstance(class_uri, URIRef):
                continue

            local_name: Optional[str] = IfcSchemaVocabulary.local_name_of(
                str(class_uri)
            )
            if local_name != IfcSchemaVocabulary.IFC_PROJECT_LOCAL_NAME:
                continue

            if subject not in subjects:
                subjects.append(subject)

        return subjects

    @classmethod
    def schemas_of(cls, graph: Graph, subject: URIRef) -> List[str]:
        """
        Return the release URIs the subject's ifcOWL types resolve to.
        """
        schemas: List[str] = []
        seen: Set[str] = set()
        class_uri: URIRef
        for class_uri in graph.objects(subject, RDF.type):
            if not isinstance(class_uri, URIRef):
                continue

            schema_uri: Optional[str] = IfcSchemaVocabulary.release_uri_of(
                str(class_uri)
            )
            if schema_uri is None or schema_uri in seen:
                continue

            seen.add(schema_uri)
            schemas.append(schema_uri)

        return schemas


class IfcProjectSchemaResolver(IfcProjectSchemaResolverPort):
    """
    Reads the schema of a project from its IfcProject declaration.

    The schema is read from one place only, the IfcProject in
    ``.__infobim__/payload/triple/ifc_project.ttl``, and it is the release
    URI its ifcOWL type resolves to. Nothing else is consulted and nothing
    is assumed: a project whose declaration is missing, ambiguous or typed
    with a vocabulary that maps to no release URI fails here rather than
    being converted under a schema nobody declared.
    """

    def resolve(self, project_path: Path) -> str:
        declaration_path: Path = IfcProjectGraph.path_of(project_path)
        if not declaration_path.is_file():
            raise IfcProjectSchemaNotResolvedError(
                f"The project declares no IfcProject at {declaration_path}."
            )

        graph: Graph = IfcProjectGraph.load(declaration_path)
        subjects: List[URIRef] = IfcProjectGraph.subjects_of(graph)
        if len(subjects) != 1:
            raise IfcProjectSchemaNotResolvedError(
                f"The project must declare exactly one IfcProject, found "
                f"{len(subjects)} in {declaration_path}."
            )

        schemas: List[str] = IfcProjectGraph.schemas_of(graph, subjects[0])
        if len(schemas) != 1:
            raise IfcProjectSchemaNotResolvedError(
                f"The IfcProject must resolve to exactly one IFC schema, "
                f"found {sorted(schemas)} in {declaration_path}."
            )

        return schemas[0]
