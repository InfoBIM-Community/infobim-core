from rdflib.namespace import RDF

from infobim.view.adapter.presentation import SCHEMA
from ontobdc.shared.domain.model.component import ComponentMetadata
from ontobdc.shared.domain.port.component import ComponentPort
from ontobdc.storage.adapter.bootstrap import StorageNamespaceBootstrap


StorageNamespaceBootstrap.initialize()
_OBDC = StorageNamespaceBootstrap.OBDC


class IfcModelTileComponent(ComponentPort):
    METADATA = ComponentMetadata(
        id="org.infobim.view.plugin.component.ifc_model_tile",
        tag="onto-infobim-ifc-model-tile",
        version="1.0.0",
        name="IFC Model Tile",
        description=(
            "Navigates the distributed logical IFC model as classes and "
            "GlobalId-addressed elements."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        required_uris=[
            str(_OBDC.DataEntity),
            str(RDF.value),
            f"{SCHEMA}encodingFormat",
        ],
        tags=["infobim", "view", "ifc", "model", "tile"],
        supported_languages=["en", "pt-BR", "pt-PT", "es"],
        min_columns=4,
        max_columns=12,
        min_rows=4,
        max_rows=8,
    )

