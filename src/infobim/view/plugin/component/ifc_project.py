from rdflib.namespace import DCTERMS

from infobim.project.domain.model.contract import IFC_PROJECT_CLASS_URI
from ontobdc.shared.domain.model.component import ComponentMetadata
from ontobdc.shared.domain.port.component import ComponentPort


class IfcProjectTileComponent(ComponentPort):
    METADATA = ComponentMetadata(
        id="org.infobim.view.plugin.component.ifc_project_tile",
        tag="onto-infobim-project-tile",
        version="1.0.0",
        name="IFC Project Tile",
        description="Presents the IfcProject as the identity of an InfoBIM Surface.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        required_uris=[IFC_PROJECT_CLASS_URI, str(DCTERMS.identifier)],
        tags=["infobim", "view", "ifc", "project", "tile"],
        supported_languages=["en", "pt-BR", "pt-PT", "es"],
        min_columns=6,
        max_columns=12,
        min_rows=7,
        max_rows=7,
        size_property=str(DCTERMS.title),
        chars_per_column=8,
    )

