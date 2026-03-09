
import ifcopenshell
from rich.console import Console
from typing import Any, Dict, Optional
from ontobdc.run.core.port.contex import CliContextPort
from infobim.module.ifc.util.element import get_all_attributes
from ontobdc.run.core.capability import Capability, CapabilityMetadata, CapabilityExecutor
from infobim.module.ifc.plugin.capability.list_property_sets import ListIfcPropertySetsCapability


class InspectElementRenderer:
    def render(self, console: Console, result: Dict[str, Any], format: str = "rich") -> None:
        console.print("[yellow]Inspect Element Capability not yet implemented.[/yellow]")
        console.print(result)


class InspectIfcElementCapability(Capability):
    """
    Capability to inspect detailed information of a specific IFC element.
    """
    METADATA = CapabilityMetadata(
        id="org.infobim.domain.ifc.capability.inspect_element",
        version="0.1.0",
        name="Inspect IFC Element",
        description="Inspects detailed information of a specific element.",
        author=["Elias M. P. Junior"],
        tags=["ifc", "bim", "inspect", "element"],
        supported_languages=["en", "pt_BR"],
        input_schema={
            "type": "object",
            "properties": {
                "ifc_path": {
                    "type": "string",
                    "uri": "org.infobim.domain.ifc.input.path",
                    "required": True,
                    "description": "Path to the IFC file.",
                },
                "global_id": {
                    "type": "string",
                    "uri": "org.infobim.domain.ifc.input.element.id",
                    "required": True,
                    "description": "GlobalId (22 chars).",
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "org.infobim.domain.ifc.element.inspect.content": {
                    "type": "object",
                    "description": "Detailed element information",
                },
            },
        },
        raises=[
             {
                "code": "org.infobim.domain.ifc.exception.file_not_found",
                "python_type": "FileNotFoundError",
                "description": "IFC file not found",
            },
            {
                "code": "org.infobim.domain.ifc.exception.element_not_found",
                "python_type": "ValueError",
                "description": "Element not found",
            }
        ],
    )

    def get_default_cli_renderer(self) -> Optional[Any]:
        return InspectElementRenderer()

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        ifc_path = context.get_parameter_value("ifc_path")
        global_id = context.get_parameter_value("global_id")

        try:
            # Load the IFC file
            model = ifcopenshell.open(ifc_path)

            # Find the element by GlobalId
            element = model.by_guid(global_id)
            if not element:
                raise ValueError(f"Element with GlobalId {global_id} not found.")

            # Get element class
            ifc_class = element.is_a()

        except FileNotFoundError:
            raise FileNotFoundError(f"IFC file not found at path: {ifc_path}")
        except ValueError as e:
            raise ValueError(f"Error finding element: {e}")

        # Reuse context for nested capability execution since parameters match
        executor = CapabilityExecutor()
        all_property_sets: Dict[str, Any] = {}
        for pset in executor.execute(ListIfcPropertySetsCapability(), context)['org.infobim.domain.ifc.pset.list.content']:
            all_property_sets[pset['name']] = pset
            all_property_sets[pset['name']]['propertySet'] = {
                'Name': pset['name'],
            }
            del(all_property_sets[pset['name']]['name'])

        # Placeholder implementation
        return {
            "org.infobim.domain.ifc.element.inspect.source": {
                "schema": model.schema,
                "type": "ifc_path",
                "value": ifc_path,
                "info": element.get_info(),
            },
            "org.infobim.domain.ifc.element.inspect.global_id": global_id,
            "org.infobim.domain.ifc.element.inspect.class": ifc_class,
            "org.infobim.domain.ifc.element.inspect.title": "Skeleton implementation",
            "org.infobim.domain.ifc.element.inspect.description": "Detailed element information",
            "org.infobim.domain.ifc.element.inspect.content": {
                "attribute": get_all_attributes(element),
                "property": all_property_sets,
            }
        }
