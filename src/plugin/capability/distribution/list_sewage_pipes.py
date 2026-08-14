
import os
import math
import argparse
import json
from rich.console import Console
from typing import Dict, Any, Optional
from stack.src.bib.core.capability.executor import CapabilityExecutor
from stack.src.tui.terminal.adapter.table_view import TableViewAdapter
from stack.src.bib.core.capability import CapabilityMetadata, Capability
from stack.src.plugin.capability.distribution.list_pipes import ListPipesCapability
from stack.src.bib.adapter.capability.cli.list_sewage_pipes import ListSewagePipesCliStrategy as ListSewagePipesCliStrategyAdapter


class ListSewagePipesCapability(ListPipesCapability):
    
    METADATA = CapabilityMetadata(
        id="org.infobim.base.capability.list_sewage_pipes",
        version="1.0.0",
        name="List Sewage Pipes",
        description="Extracts sewage pipes with specific slopes (Real vs UHC/NBR8160).",
        author="InfoBIM Team",
        tags=["ifc", "pipes", "sewage", "extraction", "reporting"],
        supported_languages=["en", "pt_BR"],
        supported_ifc_formats=["IFC2X3", "IFC4"],
        input_schema={
            "type": "object",
            "properties": {
                "ifc_path": {
                    "type": "string",
                    "description": "Absolute path to the IFC file"
                },
                "lang": {
                    "type": "string",
                    "enum": ["en", "pt_BR"],
                    "default": "en",
                    "description": "Language for output messages and columns"
                }
            },
            "required": ["ifc_path"]
        },
        output_schema={
            "type": "object",
            "properties": {
                "count": {
                    "type": "integer",
                    "description": "Total number of sewage pipes found"
                },
                "pipes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "guid": {"type": "string"},
                            "name": {"type": "string"},
                            "dn": {"type": "number"},
                            "material": {"type": "string"},
                            "z_start": {"type": "number"},
                            "z_end": {"type": "number"},
                            "length": {"type": "number"},
                            "slope_uhc": {"type": "number", "description": "Minimum slope defined by NBR8160 (%)"},
                            "slope_real": {"type": "number", "description": "Actual geometric slope (%)"}
                        }
                    }
                }
            }
        }
    )

    def get_default_cli_strategy(self, **kwargs) -> Optional[Any]:
        return ListSewagePipesCliStrategyAdapter(**kwargs)

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        result = super().execute(inputs)
        return {
            "count": result["org.ontobdc.aeco.distribution.flow.pipe.list.count"],
            "pipes": result["org.ontobdc.aeco.distribution.flow.pipe.list"]
        }
    
    def validate(self, outputs: Dict[str, Any]) -> None:
        if not outputs or "count" not in outputs or "pipes" not in outputs:
            raise ValueError("Invalid outputs for ListSewagePipesCapability.")
        pipes = outputs["pipes"]
        count = outputs["count"]
        if count != len(pipes):
            raise ValueError(f"Mismatch between count ({count}) and number of pipes ({len(pipes)}).")

    def _process_pipe(self, pipe, unit_scale) -> Dict[str, Any]:
        """
        Extend base processing to add Slope Real and Slope UHC.
        """
        # Get base data
        data = super()._process_pipe(pipe, unit_scale)
        if not data:
            return None
            
        psets = data.pop("psets", {}) # Retrieve and remove psets from final output if not needed, or keep?
        # We can keep psets if we want, but let's just use it here.
        
        # 1. Slope UHC
        slope_uhc = 0.0
        if "Pset_BR_NBR8160" in psets and "MinimalSlope" in psets["Pset_BR_NBR8160"]:
            val = psets["Pset_BR_NBR8160"]["MinimalSlope"]
            if val: slope_uhc = float(val)
            
        # 2. Slope Real
        # We need geometry info. Base class provides z_start, z_end, length (in meters)
        # We can re-calculate using the raw data in `data` which is already scaled.
        z1 = data["z_start"]
        z2 = data["z_end"]
        # Length in data is also scaled.
        # However, to be precise, slope is usually calculated on the horizontal projection.
        # But if the pipe is not vertical, length ~ horizontal length for small slopes.
        # Let's use the logic: slope = abs(dz) / dist_2d * 100
        # We don't have dist_2d easily here without re-doing geometry math or assuming length^2 = dist_2d^2 + dz^2
        
        length = data["length"]
        slope_real = 0.0
        
        dz = abs(z1 - z2)
        if length > dz:
            dist_2d = math.sqrt(length**2 - dz**2)
            if dist_2d > 0.001:
                slope_real = dz / dist_2d * 100.0
        elif length > 0:
             # Fallback if length ~ dz (vertical pipe)
             slope_real = 0.0 # Or infinity? Usually 0 for listing purposes or handle vertical
             
        data["slope_uhc"] = slope_uhc
        data["slope_real"] = slope_real
        
        return data
