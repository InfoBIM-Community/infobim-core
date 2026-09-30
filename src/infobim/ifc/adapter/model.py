from typing import Any, ClassVar, List, Optional
from pathlib import Path

from rdflib import Graph, URIRef
from rdflib.namespace import DCTERMS, RDF

from ontobdc.shared.adapter.slug import TitleSlug
from ontobdc.storage.adapter.bootstrap import (
    StorageBootstrap,
    StorageNamespaceBootstrap,
)
from infobim.ifc.adapter.schema import IfcProjectSchemaResolver
from infobim.ifc.adapter.schema_identifier import IfcSchemaIdentifier
from infobim.ifc.domain.port.model import IfcModelBootstrapPort
from infobim.ifc.domain.port.schema import IfcProjectSchemaResolverPort
from infobim.project.adapter.contract import ProjectGuard
from infobim.ifc.domain.exception.creation import (
    IfcModelNotUsableError,
    IfcSchemaIdentifierNotRegisteredError,
)


class IfcModelBootstrap(IfcModelBootstrapPort):
    """
    Creates the basic IFC model a project gets when it carries none.

    Basic is deliberate. The schema is the one the project already
    declares, resolved from its IfcProject, and the model carries that
    same IfcProject — the project's own GlobalId — so the model describes
    the project instead of introducing a second one inside it. Spatial
    structure is left out, and so are units: defining them is the next
    state of the machine, not a favour the bootstrap does.

    Where the file goes is the caller's decision, and the IfcProject is
    named after the title the container's own ontology carries. Declaring
    the file is not this class's job: the manifest hotfix states what the
    container holds.
    """

    def __init__(
        self,
        schema_resolver: Optional[IfcProjectSchemaResolverPort] = None,
    ) -> None:
        self._schema_resolver: IfcProjectSchemaResolverPort = (
            schema_resolver or IfcProjectSchemaResolver()
        )

    def create(self, project_path: Path, model_path: Path) -> Path:
        import ifcopenshell

        schema_uri: str = self._schema_resolver.resolve(project_path)
        identifier: Optional[str] = IfcSchemaIdentifier.identifier_of(schema_uri)
        if identifier is None:
            raise IfcSchemaIdentifierNotRegisteredError(
                f"No IFC reader schema is registered for the schema the "
                f"project declares: {schema_uri}."
            )

        global_id: Any = ProjectGuard.ifc_project_global_id(project_path)
        if not isinstance(global_id, str) or not global_id.strip():
            raise IfcModelNotUsableError(
                f"The project at {project_path} declares no readable "
                f"IfcProject GlobalId to create a model for."
            )

        title: str = self._project_title(project_path)
        model: Any = ifcopenshell.file(schema=identifier)
        model.create_entity(
            "IfcProject",
            GlobalId=global_id,
            Name=title,
        )

        model.write(str(model_path))

        return model_path

    @staticmethod
    def _project_title(project_path: Path) -> str:
        """
        Return the title the container's own ontology carries.
        """
        StorageNamespaceBootstrap.initialize()
        metadata_path: Path = StorageBootstrap.get_container_storage_file_path(
            project_path,
        )
        if not metadata_path.is_file():
            raise IfcModelNotUsableError(
                f"The project at {project_path} carries no container "
                f"ontology to read its title from."
            )

        graph: Graph = Graph()
        graph.parse(str(metadata_path), format="turtle")
        subjects: List[URIRef] = [
            subject
            for subject in graph.subjects(
                RDF.type,
                StorageNamespaceBootstrap.OBDC.DataContainer,
            )
            if isinstance(subject, URIRef)
        ]
        if len(subjects) != 1:
            raise IfcModelNotUsableError(
                f"The container ontology of {project_path} must describe "
                f"exactly one container, and describes {len(subjects)}."
            )

        for value in graph.objects(subjects[0], DCTERMS.title):
            title: str = str(value).strip()
            if title:
                return title

        raise IfcModelNotUsableError(
            f"The container ontology of {project_path} carries no title."
        )


class IfcProjectModelFile:
    """
    Names the IFC model file a project writes its own elements into.

    The file is named after the GlobalId of the project's IfcProject,
    slugged the way every other name this runtime puts on the filesystem
    is slugged, and sits at the root of the project. Models the project
    received from elsewhere keep their own names, so this one is never
    confused with them.
    """

    MODEL_SUFFIX: ClassVar[str] = ".ifc"

    @classmethod
    def path_of(cls, project_path: Path) -> Path:
        """
        Return where the project's own IFC model lives, whether or not it exists.
        """
        global_id: Any = ProjectGuard.ifc_project_global_id(project_path)
        if not isinstance(global_id, str) or not global_id.strip():
            raise IfcModelNotUsableError(
                f"The project at {project_path} declares no readable "
                f"IfcProject GlobalId to name its IFC model after."
            )

        slug: str = TitleSlug.of(global_id)
        if not slug:
            raise IfcModelNotUsableError(
                f"The IfcProject GlobalId '{global_id}' has no character a "
                f"file name can be made of."
            )

        return project_path / f"{slug}{cls.MODEL_SUFFIX}"
