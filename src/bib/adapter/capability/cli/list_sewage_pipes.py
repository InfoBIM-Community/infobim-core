import os
import argparse
import json
from typing import Any, Optional
from rich.console import Console
from stack.src.bib.core.capability import Capability
from stack.src.bib.core.capability.executor import CapabilityExecutor
from stack.src.tui.terminal.adapter.table_view import TableViewAdapter

class ListSewagePipesCliStrategy:
    def __init__(self, default_ifc_path: Optional[str] = None, **kwargs):
        self.default_ifc_path = default_ifc_path
    I18N = {
        "en": {
            "title": "Sewage Pipe List",
            "col_guid": "GlobalId",
            "col_name": "Name",
            "col_dn": "Nominal Diameter (mm)",
            "col_material": "Material",
            "col_z_start": "Start Elevation (m)",
            "col_z_end": "End Elevation (m)",
            "col_length": "Length (m)",
            "col_slope_uhc": "UHC Slope (%)",
            "col_slope_real": "Actual Slope (%)",
            "success": "Success! Found {count} pipes.",
            "executing": "Executing capability...",
            "running": "Running ListSewagePipesCapability on:",
            "error": "Error executing capability:"
        },
        "pt_BR": {
            "title": "Lista de Tubos de Esgoto",
            "col_guid": "GlobalId",
            "col_name": "Nome",
            "col_dn": "DN (mm)",
            "col_material": "Material",
            "col_z_start": "Cota Inicial (m)",
            "col_z_end": "Cota Final (m)",
            "col_length": "Comprimento (m)",
            "col_slope_uhc": "Declividade UHC (%)",
            "col_slope_real": "Declividade Real (%)",
            "success": "Sucesso! Encontrados {count} tubos.",
            "executing": "Executando capability...",
            "running": "Executando ListSewagePipesCapability em:",
            "error": "Erro ao executar capability:"
        }
    }
    def get_text(self, key, lang="en"):
        lang_dict = self.I18N.get(lang, self.I18N["en"])
        return lang_dict.get(key, key)
    def setup_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("ifc_path", nargs="?", default=self.default_ifc_path, help="Path to IFC file")
        parser.add_argument("--show-guid", action="store_true", help="Show GlobalId column")
        parser.add_argument("--lang", default="pt_BR", help="Language code (e.g. en, pt_BR)")
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Maximum number of pipes to display (0 = no limit)",
        )
    def run(self, console: Console, args: Any, capability: Capability) -> None:
        ifc_path = args.ifc_path
        lang = args.lang
        if not ifc_path or not os.path.exists(ifc_path):
            console.print(f"[yellow]Warning: File not found: {ifc_path}[/yellow]")
            console.print("[dim]Please provide a valid IFC path as argument.[/dim]")
            return
        console.print(f"[bold blue]{self.get_text('running', lang)}[/bold blue] {ifc_path}")
        executor = CapabilityExecutor()
        inputs = {"ifc_path": ifc_path}
        if lang:
            inputs["lang"] = lang
        result = executor.execute(capability, inputs)
        if getattr(args, "limit", 0):
            limit = max(0, int(args.limit))
            if limit > 0:
                pipes = result.get("pipes", [])
                if isinstance(pipes, list):
                    pipes = pipes[:limit]
                    result = dict(result)
                    result["pipes"] = pipes
                    result["count"] = len(pipes)
        self.render(console, args, capability, result)
    def _render_table(self, console: Console, pipes: list, args: Any, cap: Capability) -> None:
        lang = args.lang
        columns = []
        if args.show_guid and getattr(cap, "supports_global_id", False):
            columns.append((self.get_text("col_guid", lang), {"style": "dim", "width": 24, "no_wrap": True}))
        columns.extend([
            (self.get_text("col_name", lang), {"style": "cyan"}),
            (self.get_text("col_dn", lang), {"justify": "right"}),
            (self.get_text("col_material", lang), {"style": "dim"}),
            (self.get_text("col_z_start", lang), {"justify": "right"}),
            (self.get_text("col_z_end", lang), {"justify": "right"}),
            (self.get_text("col_length", lang), {"justify": "right"}),
            (self.get_text("col_slope_uhc", lang), {"justify": "right"}),
            (self.get_text("col_slope_real", lang), {"justify": "right"}),
        ])
        table = TableViewAdapter.create_table(
            title=self.get_text("title", lang),
            columns=columns
        )
        for row in pipes:
            len_val = row["length"]
            len_style = "red" if len_val > 15.0 else ""
            len_str = f"[{len_style}]{len_val:.2f}[/{len_style}]" if len_style else f"{len_val:.2f}"
            s_real = row.get("slope_real", 0.0)
            s_uhc = row.get("slope_uhc", 0.0)
            slope_style = ""
            if s_uhc > 0:
                if s_real < (s_uhc - 0.1):
                    slope_style = "red"
                elif s_real > (s_uhc + 0.1):
                    slope_style = "yellow"
            slope_real_str = f"[{slope_style}]{s_real:.2f}[/{slope_style}]" if slope_style else f"{s_real:.2f}"
            dn_disp = f"{int(row['dn'])}"
            uhc_disp = f"{s_uhc:.1f}" if s_uhc else "-"
            row_values = []
            if args.show_guid and getattr(cap, "supports_global_id", False):
                row_values.append(row["guid"])
            row_values.extend([
                row["name"],
                dn_disp,
                row["material"],
                f"{row['z_start']:.2f}",
                f"{row['z_end']:.2f}",
                len_str,
                uhc_disp,
                slope_real_str
            ])
            table.add_row(*row_values)
        console.print(table)
    def export_rich(self, console: Console, args: Any, capability: Capability, result: Any) -> None:
        lang = args.lang
        pipes = result["pipes"]
        console.print(f"[green]{self.get_text('success', lang).format(count=result['count'])}[/green]")
        self._render_table(console, pipes, args, capability)
    def render(self, console: Console, args: Any, capability: Capability, result: Any) -> None:
        fmt = getattr(args, "export", "rich")
        if fmt == "json":
            self.export_json(console, args, capability, result)
        else:
            self.export_rich(console, args, capability, result)
    def export_json(self, console: Console, args: Any, capability: Capability, result: Any) -> None:
        print(json.dumps(result, indent=2, default=str))
