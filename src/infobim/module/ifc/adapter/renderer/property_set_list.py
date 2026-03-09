
import json
from typing import Any, Dict, List
from rich.console import Console
from ontobdc.core.adapter import TableViewAdapter


class IfcPropertySetListRenderer:
    def render(self, console: Console, result: Dict[str, Any], format: str = "rich") -> None:
        if format == "json":
            self.export_json(console, result)
        else:
            self.export_rich(console, result)

    def export_rich(self, console: Console, result: Dict[str, Any]) -> None:
        psets = result.get("org.infobim.domain.ifc.pset.list.content", [])
        count = result.get("org.infobim.domain.ifc.pset.list.count", 0)
        
        if not psets:
            console.print("[yellow]No property sets found.[/yellow]")
            return

        console.print(f"[green]Property Sets found: {count}[/green]")

        for pset in psets:
            pset_name = pset.get("name", "Unknown Pset")
            properties = pset.get("properties", [])
            
            table = TableViewAdapter.create_table(
                title=f"Pset: {pset_name}",
                columns=[
                    TableViewAdapter.col("Name", kind="primary"),
                    TableViewAdapter.col("Value", kind="secondary"),
                    TableViewAdapter.col("Type", style="dim"),
                ],
            )

            for prop in properties:
                table.add_row(
                    str(prop.get("Name", "")),
                    str(prop.get("Value", "")),
                    str(prop.get("Type", ""))
                )
            
            console.print(table)
            console.print("") # Add spacing between tables

    def export_json(self, console: Console, result: Dict[str, Any]) -> None:
        print(json.dumps(result, indent=2, default=str))
