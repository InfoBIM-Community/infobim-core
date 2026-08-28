"""Generate a paginated Gantt PDF from a container's authoritative workbook."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from ....adapter.gantt_pdf import ScheduleGanttPdfExporter
from ....adapter.workbook import ScheduleWorkbookAdapter, ScheduleWorkbookError


class FourDGanttPdfCapability(TransactionCapability):
    """Resolve the 4D workbook through its datapackage and write one PDF."""

    METADATA = CapabilityMetadata(
        id="org.infobim.4d.plugin.capability.transformation.gantt_pdf",
        version="1.0.0",
        name="4D Gantt PDF",
        description=(
            "Render the IfcTask and IfcTaskTime resources declared by a "
            "container as a paginated Gantt PDF."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "4d", "gantt", "pdf", "ifc-work-schedule"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "container_path": {
                    "type": "string",
                    "required": True,
                    "description": (
                        "Container directory containing "
                        ".__ontobdc__/datapackage.json."
                    ),
                },
                "pdf_path": {
                    "type": "string",
                    "required": False,
                    "description": "Optional output PDF path.",
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "container_path": {"type": "string"},
                "datapackage_path": {"type": "string"},
                "workbook_path": {"type": "string"},
                "pdf_path": {"type": "string"},
                "task_count": {"type": "integer"},
            },
        },
        raises=[
            {
                "type": "ValueError",
                "description": (
                    "The container does not map a usable 4D workbook."
                ),
            }
        ],
        log_message={
            "info": {
                "en": "The 4D Gantt PDF was generated.",
                "pt-br": "O PDF do Gantt 4D foi gerado.",
            },
            "debug_entry": {
                "en": "Resolving the 4D workbook and rendering its Gantt PDF.",
                "pt-br": (
                    "Resolvendo o workbook 4D e renderizando seu PDF Gantt."
                ),
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return str(self.METADATA.name)

    def description(self, lang: str = "en") -> str:
        return str(self.METADATA.description)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path = Path(
            str(context.get_parameter_value("container_path") or ".")
        ).expanduser().resolve()
        try:
            workbook = ScheduleWorkbookAdapter(container_path)
        except ScheduleWorkbookError as error:
            raise ValueError(str(error)) from error

        configured_output: str = str(
            context.get_parameter_value("pdf_path") or ""
        ).strip()
        pdf_path: Path = (
            Path(configured_output).expanduser().resolve()
            if configured_output
            else workbook.workbook_path.with_suffix(".pdf")
        )
        exporter = ScheduleGanttPdfExporter(workbook.workbook_path)
        tasks = exporter.tasks()
        written_path: Path = exporter.export(pdf_path)
        return {
            "container_path": str(container_path),
            "datapackage_path": str(workbook.datapackage_path),
            "workbook_path": str(workbook.workbook_path),
            "pdf_path": str(written_path),
            "task_count": len(tasks),
        }
