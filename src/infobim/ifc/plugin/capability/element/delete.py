"""Stub capability for deleting one IFC element after explicit confirmation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class IfcElementDeleteCapability(TransactionCapability):
    """Confirm an element deletion without performing it yet.

    This first version deliberately stops after confirmation. The return
    payload makes that explicit through ``deleted=False`` and ``stub=True``.
    The confirmation decision (``confirmed``) is resolved upstream by the
    command/parameter layer -- this capability only reads it back from the
    context; it never prompts, never inspects raw CLI arguments, and never
    depends on any visual adapter.
    """

    METADATA = CapabilityMetadata(
        id="org.infobim.ifc.plugin.capability.element.delete",
        version="0.2.0",
        name="Delete IFC Element",
        description=(
            "Confirm the deletion of one IFC element. This version is a "
            "stub and never changes the IFC file. The 'confirmed' input "
            "must already be resolved by the calling command before this "
            "capability runs."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "element", "delete", "confirmation", "stub"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "ifc_path": {
                    "type": "string",
                    "required": True,
                    "description": "Path to the existing IFC file.",
                },
                "element_global_id": {
                    "type": "string",
                    "required": True,
                    "description": "GlobalId of the IFC element to delete.",
                },
                "confirmed": {
                    "type": "boolean",
                    "required": True,
                    "description": (
                        "Whether the deletion was confirmed. Resolved "
                        "upstream by the command/parameter layer, never by "
                        "this capability."
                    ),
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "ifc_path": {"type": "string"},
                "element_global_id": {"type": "string"},
                "element_class": {"type": "string"},
                "confirmed": {"type": "boolean"},
                "deleted": {"type": "boolean"},
                "stub": {"type": "boolean"},
                "status": {"type": "string"},
            },
        },
        log_message={
            "info": {
                "en": "The IFC element deletion stub finished without modifying the file.",
                "pt-br": "O stub de exclusão do elemento IFC terminou sem modificar o arquivo.",
            },
            "debug_entry": {
                "en": "Confirming the stub IFC element deletion request.",
                "pt-br": "Confirmando a solicitação stub de exclusão do elemento IFC.",
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return str(self.METADATA.name)

    def description(self, lang: str = "en") -> str:
        return str(self.METADATA.description)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        ifc_path, target = self._resolve_target(context)
        confirmed: bool = bool(context.get_parameter_value("confirmed"))
        return {
            "ifc_path": str(ifc_path),
            "element_global_id": str(target.GlobalId),
            "element_class": str(target.is_a()),
            "confirmed": confirmed,
            "deleted": False,
            "stub": True,
            "status": "stub_confirmed" if confirmed else "cancelled",
        }

    @staticmethod
    def _resolve_target(context: CliContextPort) -> Tuple[Path, Any]:
        import ifcopenshell

        ifc_path = Path(str(context.get_parameter_value("ifc_path"))).expanduser().resolve()
        if not ifc_path.is_file():
            raise ValueError(f"IFC file does not exist: {ifc_path}")

        global_id = str(context.get_parameter_value("element_global_id")).strip()
        if not global_id:
            raise ValueError("'element_global_id' is required.")

        model = ifcopenshell.open(str(ifc_path))
        try:
            target = model.by_guid(global_id)
        except RuntimeError as error:
            raise ValueError(
                f"No IFC element with GlobalId '{global_id}' was found."
            ) from error
        if target is None:
            raise ValueError(f"No IFC element with GlobalId '{global_id}' was found.")
        return ifc_path, target
