from typing import Any, ClassVar, List, Optional
from pathlib import Path

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF

from ontobdc.storage.adapter.crate import ContainerRoCrate

from infobim.ifc.domain.port.schema import IfcElementClassResolverPort
from infobim.ifc.adapter.vocabulary import IfcSchemaVocabulary
from infobim.project.domain.model.contract import ProjectContract
from infobim.ifc.domain.exception.conversion import (
    IfcElementNotFoundError,
    IfcProjectSchemaNotResolvedError,
)


class IfcElementClassResolver(IfcElementClassResolverPort):
    """
    Answers which IFC class the element carrying a GlobalId is.

    A Loader Capability is addressed by ``(schema_uri, ifc_class)``, and a
    caller of the conversion knows the element by its GlobalId alone, so the
    class has to come from the project itself before any capability can be
    selected. This reads only enough to name the class: the ifcOWL type of
    the element in the project's triples, or the IFC entity type of the same
    GlobalId in an IFC/STEP resource the RO-Crate states.

    Reading the triples before the STEP resources is not a source-priority
    rule for conversion. What a Loader Capability then extracts, and from
    which of the two source forms, is the Loader Capability's own decision;
    this only answers which capability that is.
    """

    STEP_SUFFIX: ClassVar[str] = ".ifc"
    TRIPLE_SUFFIX: ClassVar[str] = ".ttl"
    TRIPLE_FORMAT: ClassVar[str] = "turtle"

    def resolve(self, project_path: Path, schema_uri: str, element_id: str) -> str:
        namespace: Optional[str] = IfcSchemaVocabulary.namespace_of(schema_uri)
        if namespace is None:
            raise IfcProjectSchemaNotResolvedError(
                f"No ifcOWL vocabulary is mapped to the IFC schema {schema_uri}."
            )

        ifc_class: Optional[str] = self._from_triples(
            project_path,
            namespace,
            element_id,
        )
        if ifc_class is not None:
            return ifc_class

        ifc_class = self._from_step(project_path, element_id)
        if ifc_class is not None:
            return ifc_class

        raise IfcElementNotFoundError(
            f"No IFC element of the project at {project_path} carries the "
            f"GlobalId {element_id}."
        )

    @classmethod
    def _from_triples(
        cls,
        project_path: Path,
        namespace: str,
        element_id: str,
    ) -> Optional[str]:
        """
        Return the element's ifcOWL class in the project's own triples.
        """
        predicate: URIRef = URIRef(
            IfcSchemaVocabulary.term_of(
                namespace,
                IfcSchemaVocabulary.GLOBAL_ID_LOCAL_NAME,
            )
        )
        triple_path: Path
        for triple_path in cls._triple_paths(project_path):
            graph: Graph = Graph()
            try:
                graph.parse(str(triple_path), format=cls.TRIPLE_FORMAT)
            except Exception as error:
                raise IfcElementNotFoundError(
                    f"The project states triples that cannot be read while "
                    f"looking up {element_id}: {triple_path} ({error})."
                ) from error

            subject: URIRef
            for subject in graph.subjects(predicate, Literal(element_id)):
                if not isinstance(subject, URIRef):
                    continue

                class_uri: URIRef
                for class_uri in graph.objects(subject, RDF.type):
                    if not isinstance(class_uri, URIRef):
                        continue

                    local_name: Optional[str] = IfcSchemaVocabulary.local_name_of(
                        str(class_uri)
                    )
                    if local_name is not None:
                        return local_name

        return None

    @classmethod
    def _triple_paths(cls, project_path: Path) -> List[Path]:
        """
        Return the triple files the project's reserved dataset carries.
        """
        triple_directory: Path = project_path.joinpath(
            ProjectContract.DATASET_NAME,
            ProjectContract.PAYLOAD_DIRECTORY_NAME,
            ProjectContract.TRIPLE_DIRECTORY_NAME,
        )
        if not triple_directory.is_dir():
            return []

        return sorted(
            path
            for path in triple_directory.rglob(f"*{cls.TRIPLE_SUFFIX}")
            if path.is_file()
        )

    @classmethod
    def _from_step(cls, project_path: Path, element_id: str) -> Optional[str]:
        """
        Return the element's IFC entity type in an IFC/STEP resource.

        The reader is imported where it is used: a project whose elements
        live in triples converts without IfcOpenShell being importable at
        all, and one that does reach a STEP resource without it fails saying
        so rather than at import time.
        """
        step_paths: List[Path] = cls._step_paths(project_path, element_id)
        if not step_paths:
            return None

        try:
            import ifcopenshell
        except ImportError as error:
            raise IfcElementNotFoundError(
                f"The project states IFC/STEP resources but no STEP reader "
                f"is available to look up {element_id}: {error}."
            ) from error

        step_path: Path
        for step_path in step_paths:
            try:
                model: Any = ifcopenshell.open(str(step_path))
            except Exception as error:
                raise IfcElementNotFoundError(
                    f"The project states an IFC/STEP resource that cannot be "
                    f"read while looking up {element_id}: {step_path} "
                    f"({error})."
                ) from error

            element: Any = cls._element_of(model, element_id)
            if element is not None:
                return str(element.is_a())

        return None

    @staticmethod
    def _element_of(model: Any, element_id: str) -> Optional[Any]:
        """
        Return the STEP entity carrying the GlobalId, or None when absent.

        A reader reports an absent GlobalId by raising, which is the one
        outcome that means "look in the next resource" rather than "this
        resource is broken".
        """
        try:
            return model.by_guid(element_id)
        except RuntimeError:
            return None

    @classmethod
    def _step_paths(cls, project_path: Path, element_id: str) -> List[Path]:
        """
        Return the IFC/STEP resources the project's RO-Crate states.
        """
        try:
            stated: List[str] = ContainerRoCrate.file_paths(project_path)
        except ValueError as error:
            raise IfcElementNotFoundError(
                f"The project at {project_path} states no readable RO-Crate "
                f"to look {element_id} up in: {error}."
            ) from error

        return [
            project_path / relative
            for relative in stated
            if relative.lower().endswith(cls.STEP_SUFFIX)
            and (project_path / relative).is_file()
        ]
