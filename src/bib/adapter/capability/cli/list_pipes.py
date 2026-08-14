
import os
import json
import argparse
from typing import Any, Optional
from rich.console import Console
from stack.src.bib.core.capability import Capability
from stack.src.bib.core.capability.executor import CapabilityExecutor
from stack.src.tui.terminal.adapter.table_view import TableViewAdapter


class ListPipesCliStrategy:
    def __init__(self, repository: Optional[Any] = None):
        self.repository = repository
    I18N = {
        "en": {
            "title": "Generic Pipe List",
            "col_guid": "GlobalId",
            "col_name": "Name",
            "col_dn": "Nominal Diameter (mm)",
            "col_material": "Material",
            "col_z_start": "Start Elevation (m)",
            "col_z_end": "End Elevation (m)",
            "col_length": "Length (m)",
            "success": "Success! Found {count} pipes.",
            "executing": "Executing capability...",
            "running": "Running Generic ListPipesCapability on:",
            "error": "Error executing capability:"
        },
        "pt_BR": {
            "title": "Lista Genérica de Tubos",
            "col_guid": "GlobalId",
            "col_name": "Nome",
            "col_dn": "DN (mm)",
            "col_material": "Material",
            "col_z_start": "Cota Inicial (m)",
            "col_z_end": "Cota Final (m)",
            "col_length": "Comprimento (m)",
            "success": "Sucesso! Encontrados {count} tubos.",
            "executing": "Executando capability...",
            "running": "Executando Generic ListPipesCapability em:",
            "error": "Erro ao executar capability:"
        }
    }
    def get_text(self, key, lang="en"):
        lang_dict = self.I18N.get(lang, self.I18N["en"])
        return lang_dict.get(key, key)
    def setup_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("ifc_path", nargs="?", help="Path to IFC file")
        parser.add_argument("--show-guid", action="store_true", help="Show GlobalId column")
        parser.add_argument("--materials", action="store_true", help="Include material information")
        parser.add_argument("--uhc-sizing-suggest", action="store_true", help="Suggest UHC sizing (no write)")
        parser.add_argument("--lang", default="en", help="Language code (e.g. en, pt_BR)")
        parser.add_argument("--limit", type=int, default=0, help="Maximum number of pipes to display (0 = no limit)")
    def run(self, console: Console, args: Any, capability: Capability) -> None:
        ifc_path = args.ifc_path
        lang = args.lang
        if not ifc_path and self.repository:
            files = self.repository.list_files()
            if files:
                pass
        if not ifc_path:
            if self.repository:
                pass
        if ifc_path and self.repository:
            if not os.path.isabs(ifc_path):
                ifc_path = os.path.join(self.repository.base_path, ifc_path)
        if not ifc_path or not os.path.exists(ifc_path):
            console.print(f"[yellow]Warning: File not found: {ifc_path}[/yellow]")
            console.print("[dim]Please provide a valid IFC path as argument.[/dim]")
            console.print("\n[bold]Example:[/bold]")
            console.print(f"[dim]  ./infobim run {capability.metadata.id} ./data/incoming/examples/sewage_project.ifc[/dim]")
            console.print("\n")
            return
        console.print(f"[bold blue]{self.get_text('running', lang)}[/bold blue] {ifc_path}")
        executor = CapabilityExecutor()
        inputs = {"ifc_path": ifc_path}
        if args.materials:
            inputs["materials"] = True
        if args.uhc_sizing_suggest:
            inputs["uhc-sizing-suggest"] = True
        if lang:
            inputs["lang"] = lang
        result = executor.execute(capability, inputs)
        if getattr(args, "limit", 0):
            limit = max(0, int(args.limit))
            if limit > 0:
                pipes = result.get("org.ontobdc.aeco.distribution.flow.pipe.list", [])
                if isinstance(pipes, list):
                    pipes = pipes[:limit]
                    result = dict(result)
                    result["org.ontobdc.aeco.distribution.flow.pipe.list"] = pipes
                    result["org.ontobdc.aeco.distribution.flow.pipe.list.count"] = len(pipes)
        self.render(console, args, capability, result)
    def _render_table(self, console: Console, pipes: list, args: Any, cap: Capability) -> None:
        lang = args.lang
        columns = []
        if args.show_guid and getattr(cap, "supports_global_id", False):
            columns.append(
                TableViewAdapter.col(
                    self.get_text("col_guid", lang),
                    kind="secondary",
                    width=24,
                    no_wrap=True,
                )
            )
        columns.append(
            TableViewAdapter.col(
                self.get_text("col_name", lang),
                kind="primary",
            )
        )
        columns.append(
            TableViewAdapter.col(
                self.get_text("col_dn", lang),
                kind="numeric",
            )
        )
        if args.materials:
            columns.append(
                TableViewAdapter.col(
                    self.get_text("col_material", lang),
                    kind="secondary",
                )
            )
        columns.extend([
            TableViewAdapter.col(self.get_text("col_z_start", lang), kind="numeric"),
            TableViewAdapter.col(self.get_text("col_z_end", lang), kind="numeric"),
            TableViewAdapter.col(self.get_text("col_length", lang), kind="numeric"),
        ])
        table = TableViewAdapter.create_table(
            title=self.get_text("title", lang),
            columns=columns
        )
        for row in pipes:
            len_val = row["length"]
            dn_disp = f"{int(row['dn'])}"
            row_values = []
            if args.show_guid and getattr(cap, "supports_global_id", False):
                row_values.append(row["guid"])
            row_values.extend([
                row["name"],
                dn_disp
            ])
            if args.materials:
                row_values.append(row.get("material", "-"))
            row_values.extend([
                f"{row['z_start']:.2f}",
                f"{row['z_end']:.2f}",
                f"{len_val:.2f}"
            ])
            table.add_row(*row_values)
        console.print(table)
    def export_rich(self, console: Console, args: Any, capability: Capability, result: Any) -> None:
        lang = args.lang
        count = result["org.ontobdc.aeco.distribution.flow.pipe.list.count"]
        pipes = result["org.ontobdc.aeco.distribution.flow.pipe.list"]
        console.print(f"[green]{self.get_text('success', lang).format(count=count)}[/green]")
        self._render_table(console, pipes, args, capability)
    def render(self, console: Console, args: Any, capability: Capability, result: Any) -> None:
        fmt = getattr(args, "export", "rich")
        if fmt == "json":
            self.export_json(console, args, capability, result)
        else:
            self.export_rich(console, args, capability, result)
    def export_json(self, console: Console, args: Any, capability: Capability, result: Any) -> None:
        print(json.dumps(result, indent=2, default=str))
