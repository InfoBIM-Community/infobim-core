
import os
import ifcopenshell
from importlib import resources
from typing import Dict, Any, List
from .analyzer import analyze_network
from .tables import load_uhc_table, load_sizing_table
from stack.src.bib.core.capability import Capability, CapabilityMetadata


class UHCSizingCapability(Capability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.aeco.distribution.flow.pipe.sizing.uhc",
        version="0.1.0",
        name="UHC Pipe Sizing",
        description="Calculates pipe sizing using the UHC method.",
        author="Elias M. P. Junior",
        tags=["sizing", "pipes", "uhc"],
        events={
            "success": [
                "org.ontobdc.aeco.distribution.flow.pipe.sizing.uhc.suggested"
            ],
            "failure": [
                "org.ontobdc.aeco.distribution.flow.pipe.sizing.uhc.error"
            ]
        },
        input_schema={
            "type": "object",
            "properties": {
                "pipes": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "List of pipes to size"
                },
                "ifc_path": {
                    "type": "string",
                    "description": "Absolute path to the IFC file (preferred)"
                }
            }
        },
        output_schema={
            "type": "object",
            "properties": {
                "sized_pipes": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "List of pipes with sizing information"
                }
            }
        }
    )

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        ifc_path = inputs.get("ifc_path")
        sized: List[Dict[str, Any]] = []
        if ifc_path and os.path.exists(ifc_path):
            ifc_file = ifcopenshell.open(ifc_path)
            data_pkg = "stack.src.plugin.capability.distribution.uhc_sizing.data"
            appliances_csv = resources.files(data_pkg) / "nbr8160_appliances.csv"
            sizing_csv = resources.files(data_pkg) / "nbr8160_sizing.csv"
            uhc_table = load_uhc_table(str(appliances_csv))
            sizing_table = load_sizing_table(str(sizing_csv))
            graph, _sinks = analyze_network(ifc_file, uhc_table, sizing_table, sink_name_filter=None, debug_callback=None)
            for guid, node in graph.items():
                el = node["element"]
                if el.is_a("IfcPipeSegment") or el.is_a("IfcFlowSegment"):
                    sized.append({
                        "guid": guid,
                        "name": el.Name if el.Name else "Unnamed",
                        "suggested_dn": node["min_dn"],
                        "suggested_slope": node["min_slope"],
                        "accumulated_uhc": node["accumulated_uhc"]
                    })
        else:
            pipes = inputs.get("pipes", [])
            for p in pipes:
                suggested_dn = float(p.get("dn", 0.0)) if p.get("dn") is not None else 0.0
                sized.append({
                    "guid": p.get("guid"),
                    "name": p.get("name"),
                    "suggested_dn": suggested_dn
                })
        return {"sized_pipes": sized}
