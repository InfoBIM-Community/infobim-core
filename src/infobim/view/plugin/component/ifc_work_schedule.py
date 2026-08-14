from infobim.project.domain.model.contract import INFOBIM_NS
from ontobdc.shared.domain.model.component import ComponentMetadata
from ontobdc.shared.domain.port.component import ComponentPort


class IfcWorkScheduleTileComponent(ComponentPort):
    """BIM-specific schedule summary independent of XLSX worksheets."""

    METADATA = ComponentMetadata(
        id="org.infobim.view.plugin.component.ifc_work_schedule_tile",
        tag="onto-infobim-ifc-work-schedule-tile",
        version="1.0.0",
        name="IFC Work Schedule Tile",
        description="Presents an InfoBIM IfcWorkSchedule from semantic data.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        required_uris=[f"{INFOBIM_NS}IfcWorkSchedule"],
        tags=["infobim", "view", "ifc", "schedule", "tile"],
        supported_languages=["en", "pt-br"],
        min_columns=3,
        max_columns=8,
        min_rows=2,
        max_rows=5,
    )

