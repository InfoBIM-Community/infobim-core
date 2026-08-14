import os
import sys
import argparse
import importlib.util
import subprocess
from typing import Optional
from rich.console import Console
from stack.src.tui.util.path import get_config_path, load_config
from stack.src.tui.util.translation import get_translated_message
from stack.src.tui.core.port.ui.screen import TerminalScreenPort, TerminalScreenSpinnerPort, TerminalScreenTreeContentPort
from stack.src.tui.util.selector import FileSelector, SimpleMenuSelector, Keyboard
from ontobdc.tmp.aeco.core.port.ifc.repository import IfcFileRepositoryPort
from ontobdc.tmp.aeco.adapter.ifc.hierarchy.adapter import IfcFileTreeAdapter
from ontobdc.tmp.aeco.adapter.ifc.repository.local import LocalIfcFileRepositoryAdapter
from ontobdc.tmp.aeco.adapter.ifc.repository.docker import DockerIfcFileRepositoryAdapter
import yaml


def load_adapter_module(config):
    template_rel_path = config.get('template', {}).get('path')
    if not template_rel_path:
        raise ValueError("Template path not found in configuration")
    config_dir = os.path.dirname(get_config_path())
    template_path = os.path.join(config_dir, template_rel_path)
    adapter_file = os.path.join(template_path, "adapter", "ui", "screen.py")
    if not os.path.exists(adapter_file):
        raise FileNotFoundError(f"Adapter file not found at {adapter_file}")
    spec = importlib.util.spec_from_file_location("screen_adapter", adapter_file)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load spec from {adapter_file}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["screen_adapter"] = module
    spec.loader.exec_module(module)
    if not hasattr(module, "TerminalScreenAdapter"):
        raise ImportError(f"Class TerminalScreenAdapter not found in {adapter_file}")
    return module


def load_narrative_chapters(config) -> list[dict]:
    lang = config.get("language", "en")
    template_rel_path = config.get("template", {}).get("path", "")
    if not template_rel_path:
        return []
    config_dir = os.path.dirname(get_config_path())
    template_path = os.path.join(config_dir, template_rel_path)
    translation_dir = os.path.join(template_path, "translation")
    translation_file = os.path.join(translation_dir, f"{lang}.yaml")
    if not os.path.exists(translation_file) and lang != "en":
        translation_file = os.path.join(translation_dir, "en.yaml")
    if not os.path.exists(translation_file):
        return []
    try:
        with open(translation_file, 'r') as f:
            data = yaml.safe_load(f) or {}
        chapters = data.get("narrative", {}).get("chapters", [])
        opts = []
        for ch in chapters:
            if isinstance(ch, str):
                opts.append({"label": ch, "value": ch})
            elif isinstance(ch, dict):
                label = ch.get("label") or ch.get("name") or ch.get("title") or "Chapter"
                value = ch.get("value") or ch.get("id") or label
                opts.append({"label": label, "value": value})
        return opts
    except Exception:
        return []


def main() -> None:
    parser = argparse.ArgumentParser(description="InfoBIM Narrative TUI")
    args = parser.parse_args()

    config = load_config()
    adapter_module = load_adapter_module(config)
    AdapterClass: TerminalScreenPort = adapter_module.TerminalScreenAdapter
    SpinnerAdapterClass: Optional[TerminalScreenSpinnerPort] = getattr(adapter_module, "TerminalScreenSpinnerAdapter", None)
    TerminalScreenTreeContentClass: Optional[TerminalScreenTreeContentPort] = getattr(adapter_module, "TerminalScreenTreeContentAdapter", None)

    console: TerminalScreenPort = AdapterClass()

    if config.get("engine", {}).get("ifc") == "docker":
        repo_adapter: IfcFileRepositoryPort = DockerIfcFileRepositoryAdapter()
    else:
        repo_adapter: IfcFileRepositoryPort = LocalIfcFileRepositoryAdapter('./data/incoming')

    def init_tree_adapter():
        return IfcFileTreeAdapter(repo_adapter)

    spinner: Optional[TerminalScreenSpinnerPort] = None
    if SpinnerAdapterClass:
        spinner_msg = get_translated_message(
            config,
            "spinner.narrative.search_files",
            default="Searching all IFC files in"
        )
        spinner = SpinnerAdapterClass(f"  {spinner_msg} {repo_adapter.base_path}...")

    if spinner:
        tree_adapter = console.render(spinner=spinner, work=init_tree_adapter)
        if tree_adapter is None or isinstance(tree_adapter, Exception):
            if isinstance(tree_adapter, Exception):
                raise tree_adapter
            tree_adapter = IfcFileTreeAdapter(repo_adapter)
    else:
        tree_adapter = IfcFileTreeAdapter(repo_adapter)

    if TerminalScreenTreeContentClass:
        files = []
        if hasattr(tree_adapter, 'get_files'):
            files = tree_adapter.get_files()
        elif hasattr(repo_adapter, 'list_files'):
            files = repo_adapter.list_files()

        if files:
            selector = FileSelector()
            menu_selector = SimpleMenuSelector()
            while True:
                selected_file = selector.select_file(files, title="Select an IFC File")
                if selected_file:
                    chapters = load_narrative_chapters(config)
                    if not chapters:
                        chapters = [{"label": "Technical Specifications", "value": "technical_specifications"},
                                    {"label": "Design Narrative", "value": "design_narrative"},
                                    {"label": "Project Description", "value": "project_description"},
                                    {"label": "Scope of Work", "value": "scope_of_work"},
                                    {"label": "Descriptive Report", "value": "descriptive_report"}]
                    while True:
                        chosen = menu_selector.select_option(
                            chapters,
                            title=f"Chapters for {os.path.basename(selected_file)}"
                        )
                        if chosen:
                            console_rich = Console()
                            console_rich.print(f"\n[green]Selected chapter:[/green] {chosen}")
                            keyboard = Keyboard()
                            keyboard()
                        else:
                            break
                else:
                    console.render(content="[yellow]Selection cancelled.[/yellow]")
                    break
        else:
            tree_content = TerminalScreenTreeContentClass(tree_adapter)
            console.render(tree=tree_content.render())
    else:
        console.render(tree=tree_adapter.build_tree())


if __name__ == "__main__":
    main()
