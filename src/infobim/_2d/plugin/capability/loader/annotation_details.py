from typing import Any, ClassVar, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import DataLoaderCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim._2d.domain.port.viewer import DxfViewerSessionPort


class DxfAnnotationDetailsCapability(DataLoaderCapability):
    """
    Ask, on the open 2D viewer window, for the details of the annotation.

    A form asks for the title, the text and the author. They are left in the
    context under the keys OntoBDC reads them from. This is the last thing
    done on the window, so it is closed here, whether the form was filled
    in or cancelled.
    """

    SESSION_KEY: ClassVar[str] = "dxf_viewer_session"
    TITLE_KEY: ClassVar[str] = "annotation_title"
    TEXT_KEY: ClassVar[str] = "annotation_text"
    AUTHOR_KEY: ClassVar[str] = "annotation_author"

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id="org.infobim._2d.plugin.capability.loader.dxf_annotation_details",
        version="1.0.0",
        name="DXF Annotation Details Filled",
        description=(
            "Ask for the title, text and author of the annotation on the "
            "open InfoBIM 2D viewer window, then close it."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "2d", "dxf", "viewer", "annotation"],
        supported_languages=["en"],
        input_schema={
            "type": "object",
            "properties": {
                SESSION_KEY: {"type": DxfViewerSessionPort, "required": True},
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                TITLE_KEY: {"type": "string"},
                TEXT_KEY: {"type": "string"},
                AUTHOR_KEY: {"type": "string"},
            },
        },
    )

    KEYS_BY_FIELD: ClassVar[Dict[str, str]] = {
        "title": TITLE_KEY,
        "text": TEXT_KEY,
        "author": AUTHOR_KEY,
    }

    def label(self, lang: str = "en") -> str:
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        session: DxfViewerSessionPort = context.get_parameter_value(self.SESSION_KEY)
        try:
            details: Dict[str, str] = session.request_annotation_details()
        finally:
            session.close()

        answer: Dict[str, Any] = {}
        field: str
        key: str
        for field, key in self.KEYS_BY_FIELD.items():
            if field in details:
                context.set_parameter_value(key, details[field])
                answer[key] = details[field]
            else:
                context.delete_parameter(key)
        return answer
