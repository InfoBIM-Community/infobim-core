import argparse
import json
from typing import Any
from rich.console import Console
from stack.src.bib.core.capability import Capability
from stack.src.bib.core.capability.executor import CapabilityExecutor
from stack.src.tui.terminal.adapter.table_view import TableViewAdapter

class ListMaterialsCliStrategy:
    def __init__(self, repository=None, **kwargs):
        self.repository = repository
    def setup_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("ifc_path", help="Path to IFC file")
    def run(self, console: Console, args: Any, capability: Capability) -> None:
        executor = CapabilityExecutor()
        inputs = {"ifc_path": args.ifc_path, "fields": ["GlobalId", "Name"]}
        result = executor.execute(capability, inputs)
        self.render(console, args, capability, result)
    def export_rich(self, console: Console, args: Any, capability: Capability, result: Any) -> None:
        count = result["org.ontobdc.aeco.material.list.count"]
        items = result["org.ontobdc.aeco.material.list"]
        console.print(f"[green]Materials found: {count}[/green]")
        table = TableViewAdapter.create_table(
            title="Materials",
            columns=[
                ("GlobalId", {"style": "dim", "width": 24, "no_wrap": True}),
                ("Name", {"style": "cyan"}),
                ("Material", {"style": "magenta"})
            ]
        )
        for row in items:
            table.add_row(row.get("GlobalId", "-"), row.get("Name", "-"), row.get("Material", "-"))
        console.print(table)
    def render(self, console: Console, args: Any, capability: Capability, result: Any) -> None:
        fmt = getattr(args, "export", "rich")
        if fmt == "json":
            self.export_json(console, args, capability, result)
        else:
            self.export_rich(console, args, capability, result)
    def export_json(self, console: Console, args: Any, capability: Capability, result: Any) -> None:
        print(json.dumps(result, indent=2, default=str))
