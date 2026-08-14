import os
import sys
from time import sleep
from typing import Optional
import yaml
import argparse
import subprocess
import importlib.util
from rich.console import Console
from stack.src.tui.util.translation import get_translated_message
from ontobdc.tmp.aeco.core.port.ifc.repository import IfcFileRepositoryPort
from ontobdc.tmp.aeco.adapter.ifc.hierarchy.adapter import IfcFileTreeAdapter
from ontobdc.tmp.aeco.adapter.ifc.repository.local import LocalIfcFileRepositoryAdapter
from ontobdc.tmp.aeco.adapter.ifc.repository.docker import DockerIfcFileRepositoryAdapter
from stack.src.tui.util.path import get_message_box_script, get_config_path, load_config
from stack.src.tui.core.port.ui.screen import TerminalScreenPort, TerminalScreenSpinnerPort, TerminalScreenTreeContentPort
from stack.src.tui.util.selector import FileSelector, SimpleMenuSelector, Keyboard


def load_adapter_module(config):
    # Get template path from config
    # Expecting config structure: template: path: "..."
    template_rel_path = config.get('template', {}).get('path')
    if not template_rel_path:
        raise ValueError("Template path not found in configuration")
    
    # Resolve absolute path to template
    # Template path is relative to config file location (stack/src/tui/)
    config_dir = os.path.dirname(get_config_path())
    template_path = os.path.join(config_dir, template_rel_path)
    
    # Adapter is expected at adapter/ui/screen.py inside template
    adapter_file = os.path.join(template_path, "adapter", "ui", "screen.py")

    if not os.path.exists(adapter_file):
        raise FileNotFoundError(f"Adapter file not found at {adapter_file}")
        
    # Dynamic import
    spec = importlib.util.spec_from_file_location("screen_adapter", adapter_file)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load spec from {adapter_file}")
        
    module = importlib.util.module_from_spec(spec)
    sys.modules["screen_adapter"] = module
    spec.loader.exec_module(module)
    
    if not hasattr(module, "TerminalScreenAdapter"):
        raise ImportError(f"Class TerminalScreenAdapter not found in {adapter_file}")
        
    return module


def show_error_box(exc: Exception):
    # Call the bash message box script
    script_path = get_message_box_script()
    
    if os.path.exists(script_path):
        subprocess.run(["bash", script_path, "RED", "Error", "TUI Runtime Error", str(exc)])
    else:
        # Fallback if script not found (should not happen if structure is correct)
        print(f"Error: {exc}")
        print(f"Also failed to find message box script at {script_path}")


def check_ifc_engine(config) -> None:
    """
    Checks if the IFC engine is available in config.
    If not, raises an Exception with translated message.
    """
    ifc_engine = config.get("engine", {}).get("ifc")
    if ifc_engine and ifc_engine in ['docker', 'api']:
        return

    # Engine not found, resolve warning message
    message = get_translated_message(
        config,
        "exception.message.ifc_engine_not_found",
        "IFC engine not found. Let's set it up."
    )

    # Raise exception to be caught by main
    raise Exception(message)


def configure_engine(config):
    console = Console()
    console.clear()
    
    # Header similar to bash script style
    console.rule(style="bright_black")
    console.print("[bold cyan]IFC Engine Configuration[/]", justify="left")
    console.rule(style="bright_black")
    
    console.print("\nPlease select an IFC Engine:")
    console.print("[1] Docker [green](Recommended)[/]")
    console.print("[2] API [dim](Coming soon)[/]")
    
    # Exit option separated
    console.print("")
    console.print("[0] Exit")
    
    while True:
        choice = console.input("\nEnter your choice [1]: ")
        if not choice:
            choice = "1"
            
        if choice == "1":
            engine = "docker"
            break
        elif choice == "2":
            console.print("[yellow]API engine is currently disabled. Please select Docker.[/]")
        elif choice == "0":
            console.print("\n[yellow]Exiting configuration...[/]")
            return False
        else:
            console.print("[red]Invalid choice. Please try again.[/]")
            
    # Update config
    if "engine" not in config:
        config["engine"] = {}
    config["engine"]["ifc"] = engine
    
    config_path = get_config_path()
    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)
        
    console.print(f"\n[green]Engine configured to '{engine}'.[/]")
    console.print("[yellow]Please run './infobim ifc' to start the application.[/]")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="InfoBIM IFC TUI")
    parser.add_argument("--config", action="store_true", help="Configure IFC engine")
    args = parser.parse_args()

    config = load_config()
    
    if args.config:
        configure_engine(config)
        return

    # Check engine before loading UI
    # If check fails, it raises Exception which is caught below
    # check_ifc_engine(config)

    adapter_module = load_adapter_module(config)
    AdapterClass: TerminalScreenPort = adapter_module.TerminalScreenAdapter
    SpinnerAdapterClass: Optional[TerminalScreenSpinnerPort] = getattr(adapter_module, "TerminalScreenSpinnerAdapter", None)
    TerminalScreenTreeContentClass: Optional[TerminalScreenTreeContentPort] = getattr(adapter_module, "TerminalScreenTreeContentAdapter", None)

    # Instantiate the adapter
    console: TerminalScreenPort = AdapterClass()

    if config.get("engine", {}).get("ifc") == "docker":
        repo_adapter: IfcFileRepositoryPort = DockerIfcFileRepositoryAdapter()
    else:
        repo_adapter: IfcFileRepositoryPort = LocalIfcFileRepositoryAdapter('./data/incoming')

    # Define the work function (instantiating the adapter)
    def init_tree_adapter():
        return IfcFileTreeAdapter(repo_adapter)

    # Render the screen
    spinner: Optional[TerminalScreenSpinnerPort] = None

    if SpinnerAdapterClass:
        # Get translated message
        spinner_msg = get_translated_message(
            config,
            "spinner.ifc.search_files",
            default="Searching all IFC files in"
        )

        # Initialize with mandatory message
        spinner = SpinnerAdapterClass(f"  {spinner_msg} {repo_adapter.base_path}...")

    if spinner:
        # Run spinner while initializing tree adapter + 5s
        tree_adapter = console.render(spinner = spinner, work = init_tree_adapter)
        # If interrupted or failed, tree_adapter might be None or Exception. 
        # For this context, we assume success or handle None below.
        if tree_adapter is None or isinstance(tree_adapter, Exception):
             # Fallback if something went wrong or just exited
             if isinstance(tree_adapter, Exception):
                 raise tree_adapter
             tree_adapter = IfcFileTreeAdapter(repo_adapter)
    else:
        # No spinner, just initialize
        tree_adapter = IfcFileTreeAdapter(repo_adapter)

    if TerminalScreenTreeContentClass:
        # Try interactive selection first
        files = []
        if hasattr(tree_adapter, 'get_files'):
            files = tree_adapter.get_files()
        elif hasattr(repo_adapter, 'list_files'):
            files = repo_adapter.list_files()
            
        if files:
            selector = FileSelector()
            menu_selector = SimpleMenuSelector()
            # Clear screen before showing menu? FileSelector uses screen=True so it handles it.
            
            while True:
                selected_file = selector.select_file(files, title="Select an IFC File")
                
                if selected_file:
                    # Show action menu for selected file
                    options = [
                        {"label": "List Pipes", "value": "infobim.capability.list_pipes"},
                        {"label": "List Sewage Pipes", "value": "org.infobim.base.capability.list_sewage_pipes"}
                    ]
                    
                    while True:
                        action = menu_selector.select_option(
                            options, 
                            title=f"Action for {os.path.basename(selected_file)}"
                        )
                        
                        if action:
                            # Execute the selected capability using the infobim wrapper script
                            # This ensures correct environment setup and path handling
                            # Path to project root (4 levels up from stack/src/tui/terminal/ifc.py)
                            current_dir = os.path.dirname(os.path.abspath(__file__))
                            project_root = os.path.abspath(os.path.join(current_dir, "../../../../"))
                            infobim_script = os.path.join(project_root, "infobim")
                            
                            # Ensure selected_file is absolute
                            # If it comes from repo adapter, it might be relative to repo base
                            # But FileSelector returns whatever value is put in.
                            # The repo adapter list_files returns relative paths usually?
                            # Let's check if we can resolve it against repo base if needed.
                            # repo_adapter.base_path is available.
                            
                            abs_file_path = selected_file
                            if not os.path.isabs(selected_file):
                                # Try to resolve against current dir first (if user ran from there)
                                # Or repo base path
                                if hasattr(repo_adapter, 'base_path'):
                                    abs_file_path = os.path.join(repo_adapter.base_path, selected_file)
                                else:
                                    abs_file_path = os.path.abspath(selected_file)
                            
                            # Build command: ./infobim run <capability_id> <ifc_path>
                            cmd = ["bash", infobim_script, "run", action, abs_file_path]
                            
                            # Clear screen manually
                            console.clear()
                            
                            try:
                                # We use subprocess.run to let the capability take over the terminal
                                subprocess.run(cmd, check=False)
                            except Exception as e:
                                console.print(f"[red]Error executing capability: {e}[/red]")
                            
                            # Wait for user input to continue, so they can see the output
                            console_rich = Console()
                            console_rich.print("\n[dim]Press any key to return...[/dim]")
                            
                            keyboard = Keyboard()
                            keyboard() # Wait for keypress
                        else:
                            # ESC pressed in action menu -> Back to file selection
                            break
                else:
                    # ESC pressed in menu -> Exit app
                    console.render(content="[yellow]Selection cancelled.[/yellow]")
                    break
        else:
            # Fallback to static tree if no files found (or empty list)
            tree_content = TerminalScreenTreeContentClass(tree_adapter)
            console.render(tree=tree_content.render())
    else:
        # Fallback if adapter not found
        console.render(tree=tree_adapter.build_tree())


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        show_error_box(exc)
