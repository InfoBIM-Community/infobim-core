
import json
from typing import Any, Dict, List
from rich.console import Console
from ontobdc.core.adapter import TableViewAdapter


class IfcBuildingListRenderer:
    def render(self, console: Console, result: Dict[str, Any], format: str = "rich") -> None:
        if format == "json":
            self.export_json(console, result)
        else:
            self.export_rich(console, result)

    def export_rich(self, console: Console, result: Dict[str, Any]) -> None:
        buildings = result.get("org.infobim.domain.ifc.building.list.content", [])
        count = result.get("org.infobim.domain.ifc.building.list.count", 0)
        
        if not buildings:
            console.print("[yellow]No buildings found.[/yellow]")
            return

        console.print(f"\n[green]Buildings found: {count}[/green]\n")

        for building in buildings:
            building_name = building.get("Name", "Unknown Building")
            storeys = building.get("Storeys", [])
            
            table = TableViewAdapter.create_table(
                title=f"Building: {building_name} ({building.get('GlobalId', '')})",
                columns=[
                    TableViewAdapter.col("Name", kind="primary"),
                    TableViewAdapter.col("Elevation (m)", kind="secondary", justify="right"),
                    TableViewAdapter.col("GlobalId", style="dim"),
                ],
            )

            if not storeys:
                 # If no storeys, add a row indicating that
                 table.add_row("-", "-", "-")
            else:
                for storey in storeys:
                    table.add_row(
                        str(storey.get("Name", "")),
                        str(storey.get("Elevation", "")),
                        str(storey.get("GlobalId", ""))
                    )
            
            console.print(table)
            console.print("") # Add spacing between tables

    def export_json(self, console: Console, result: Dict[str, Any]) -> None:
        print(json.dumps(result, indent=2, default=str))
