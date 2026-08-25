from rdflib.namespace import DCTERMS

from infobim.project.domain.model.contract import INFOBIM_NS
from ontobdc.shared.domain.model.component import ComponentMetadata
from ontobdc.shared.domain.port.component import ComponentPort


class IfcWorkScheduleTileComponent(ComponentPort):
    """BIM-specific schedule summary independent of XLSX worksheets.

    Sized and laid out as WorkStream's sibling: both summarize one named
    entity with a title, an identifier and a description, and both keep
    their remaining fields behind the Tile's own expand toggle. The size
    envelope is deliberately identical to `WorkStreamTileComponent`'s so a
    Surface carrying both places them as a matched pair rather than as a
    large card next to a small one.
    """

    METADATA = ComponentMetadata(
        id="org.infobim.view.plugin.component.ifc_work_schedule_tile",
        tag="onto-infobim-ifc-work-schedule-tile",
        version="1.0.0",
        name="IFC Work Schedule Tile",
        description="Presents an InfoBIM IfcWorkSchedule from semantic data.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        required_uris=[f"{INFOBIM_NS}IfcWorkSchedule"],
        tags=["infobim", "view", "ifc", "schedule", "tile"],
        supported_languages=["en", "pt-BR", "pt-PT", "es"],
        min_columns=6,
        max_columns=None,
        min_rows=3,
        max_rows=3,
        size_property=str(DCTERMS.title),
        chars_per_column=4,
    )

