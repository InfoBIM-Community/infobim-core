
import json
from typing import Any, Dict
from rich.console import Console
from ontobdc.core.adapter import TableViewAdapter


class IfcElementsListRenderer:
    def render(self, console: Console, result: Dict[str, Any], format: str = "rich") -> None:
        if format == "json":
            self.export_json(console, result)
        else:
            self.export_rich(console, result)

    def export_rich(self, console: Console, result: Dict[str, Any]) -> None:
        # Check for generic list keys
        elements = result.get("org.infobim.domain.ifc.element.list.content")
        count = result.get("org.infobim.domain.ifc.element.list.count")
        
        # Check for typed list keys if generic not found
        if elements is None:
            elements = result.get("org.infobim.domain.ifc.element.list_by_type.content", [])
            count = result.get("org.infobim.domain.ifc.element.list_by_type.count", 0)
            
        if not elements:
            console.print("[yellow]No elements found.[/yellow]")
            return

        # Determine columns from the first element
        first_element = elements[0]
        # keys = list(first_element.keys())
        # Prioritize some keys
        priority_keys = ["GlobalId", "Name", "PredefinedType", "Material"]
        other_keys = [k for k in first_element.keys() if k not in priority_keys]
        columns_keys = priority_keys + other_keys

        columns = [TableViewAdapter.col("#", kind="index")]
        for key in columns_keys:
             if key == "Name":
                 columns.append(TableViewAdapter.col(key, kind="primary"))
             elif key == "GlobalId":
                 columns.append(TableViewAdapter.col(key, style="green"))
             elif key == "PredefinedType":
                 columns.append(TableViewAdapter.col(key, style="magenta"))
             elif key == "Material":
                 columns.append(TableViewAdapter.col(key, style="yellow"))
             else:
                 columns.append(TableViewAdapter.col(key, kind="secondary"))

        table = TableViewAdapter.create_table(
            title=f"IFC Elements ({count})",
            columns=columns,
        )
        
        for idx, element in enumerate(elements, start=1):
            row = [str(idx)]
            for key in columns_keys:
                row.append(str(element.get(key, "")))
            table.add_row(*row)

        console.print(table)

    def export_json(self, console: Console, result: Dict[str, Any]) -> None:
        print(json.dumps(result, indent=2, default=str))
