import argparse
import json
from typing import Any, Optional
from rich.console import Console
from stack.src.bib.core.capability import Capability
from stack.src.bib.core.capability.executor import CapabilityExecutor
from stack.src.tui.terminal.adapter.table_view import TableViewAdapter

class ProjectUnitsCliStrategy:
    def __init__(self, repository=None, **kwargs):
        self.repository = repository
    def setup_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("ifc_path", help="Path to IFC file")
        parser.add_argument("--lang", default="en")
    def run(self, console: Console, args: Any, capability: Capability) -> None:
        executor = CapabilityExecutor()
        inputs = {"ifc_path": args.ifc_path}
        result = executor.execute(capability, inputs)
        self.render(console, args, capability, result)
    def render(self, console: Console, args: Any, capability: Capability, result: Any) -> None:
        fmt = getattr(args, "export", "rich")
        if fmt == "json":
            self.export_json(console, args, capability, result)
        else:
            self.export_rich(console, args, capability, result)
    def export_json(self, console: Console, args: Any, capability: Capability, result: Any) -> None:
        print(json.dumps(result, indent=2, default=str))
    def export_rich(self, console: Console, args: Any, capability: Capability, result: Any) -> None:
        summary = f"Unit: {result.get('length_unit')} | Scale: {result.get('length_scale')} | Schema: {result.get('schema')}"
        console.print(summary)
        columns = [
            ("Unit Type", {"style": "cyan"}),
            ("Name", {"style": "magenta"}),
            ("Prefix", {"style": "dim"}),
            ("Kind", {"style": "green"}),
            ("Elements", {"justify": "right"})
        ]
        table = TableViewAdapter.create_table(title="Project Units", columns=columns)
        for u in result.get("units", []):
            table.add_row(
                u.get("unit_type") or "-",
                u.get("name") or "-",
                u.get("prefix") or "-",
                u.get("kind") or "-",
                str(u.get("elements_count", 0))
            )
        console.print(table)
