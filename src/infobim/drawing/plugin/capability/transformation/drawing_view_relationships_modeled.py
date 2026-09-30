from typing import Any, Dict, List
from pathlib import Path

from rdflib import Graph

from ontobdc.shared.adapter.shacl import ShaclValidator
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.shacl import ShaclValidationReport
from ontobdc.shared.domain.exception.shacl import ShaclConformanceError
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.drawing.adapter.taxonomy import DrawingViewContextKeys
from infobim.drawing.adapter.view_iri import DrawingViewIris
from infobim.project.adapter.contract import ProjectGuard
from infobim.drawing.domain.model.view import DrawingView
from infobim.drawing.adapter.view_context import DrawingViewContext
from infobim.drawing.adapter.view_relationship import (
    DrawingViewShapes,
    DrawingViewRelationshipModel,
    DrawingViewRelationshipGraphs,
    DrawingViewRelationshipRepository,
)
from infobim.drawing.adapter.transformation_payload import TransformationPayloadPath


class DrawingViewRelationshipsModeledCapability(TransformationCapability):
    """
    Model how a sheet relates to the views extracted from it, and validate it.

    The sheet and its view DXFs are declared as ICDD documents linked from
    the sheet to each view, and as an OntoSTEP presentation area with its
    presentation views. The triples are persisted in the project's ICDD
    dataset, read back and validated against the canonical SHACL shapes;
    a graph that does not conform is removed and the state fails.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.drawing.plugin.capability.transformation.target."
            "drawing_view_relationships_modeled"
        ),
        version="0.1.0",
        name="Drawing View Relationships Modeled",
        description=(
            "Model the sheet and its extracted views as ICDD documents and "
            "links and as OntoSTEP presentation entities, persist them in "
            "the project's dataset and validate them with SHACL."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "drawing", "view", "icdd", "ontostep", "shacl"],
        supported_languages=["en"],
        input_schema={
            "type": "object",
            "properties": {
                DrawingViewContextKeys.CONTAINER_PATH: {
                    "type": "string",
                    "required": True,
                },
                DrawingViewContextKeys.DRAWING_SOURCE_PATH: {
                    "type": "string",
                    "required": True,
                },
                DrawingViewContextKeys.DRAWING_PATH: {
                    "type": "string",
                    "required": True,
                },
                DrawingViewContextKeys.VIEWS: {"type": list, "required": True},
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                DrawingViewContextKeys.RELATIONSHIPS: {"type": "object"},
            },
        },
        log_message={
            "info": {
                "en": "The relationships of the sheet and its views conform to SHACL.",
            },
            "debug_entry": {"en": "Modelling the relationships of the sheet views."},
        },
    )

    def label(self, lang: str = "en") -> str:
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        project: Path = self._path(context, DrawingViewContextKeys.CONTAINER_PATH)
        sheet: Path = self._path(context, DrawingViewContextKeys.DRAWING_SOURCE_PATH)
        views: List[DrawingView] = DrawingViewContext.views(context)

        graphs: DrawingViewRelationshipGraphs = DrawingViewRelationshipModel.of(
            sheet,
            views,
            DrawingViewIris(
                self._project_global_id(project),
                TransformationPayloadPath.identifier_for(sheet),
            ),
        )
        repository: DrawingViewRelationshipRepository = DrawingViewRelationshipRepository(
            project,
            TransformationPayloadPath.identifier_for(
                self._path(context, DrawingViewContextKeys.DRAWING_PATH)
            ),
        )
        repository.write(graphs)
        persisted: Graph = repository.read()
        report: ShaclValidationReport = ShaclValidator.validate(
            persisted, DrawingViewShapes.graph()
        )
        if not report.conforms:
            repository.remove()
            raise ShaclConformanceError(
                f"The relationships of the sheet {sheet.name}", report
            )

        relationships: Dict[str, Any] = {
            "linkset_path": str(repository.paths[0]),
            "presentation_path": str(repository.paths[1]),
            "triples": len(persisted),
            "shacl_conforms": report.conforms,
        }
        context.set_parameter_value(
            DrawingViewContextKeys.RELATIONSHIPS, relationships
        )
        return {DrawingViewContextKeys.RELATIONSHIPS: relationships}

    @staticmethod
    def _path(context: CliContextPort, key: str) -> Path:
        return Path(RequiredParameter.of(context, key)).expanduser().resolve()

    @staticmethod
    def _project_global_id(project: Path) -> str:
        global_id: Any = ProjectGuard.ifc_project_global_id(project)
        if not isinstance(global_id, str) or not global_id.strip():
            raise ValueError(
                f"The project at {project} declares no IfcProject GlobalId to "
                "name its documents after."
            )
        return global_id.strip()
