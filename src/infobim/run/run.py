
import os
import sys
from rich.console import Console
from ontobdc.run.core.capability import Capability
from ontobdc.run.core.port.contex import CliContextPort
from ontobdc.run.adapter.contex import CliContextResolver
from ontobdc.run.adapter.selector import SimpleMenuSelector
from ontobdc.run.run import log, get_all_capabilities, run_capability
from ontobdc.run.ui import YELLOW, RED, print_message_box, GRAY, CYAN

try:
    from ontobdc.run.util import setup_project_root
except ImportError:
    setup_project_root = None


if setup_project_root:
    setup_project_root()

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'
WHITE='\033[1;37m'
RESET='\033[0m'
CONFIG_JSON="${SCRIPT_DIR}/config.json"
FULL_HLINE="----------------------------------------"


def show_help():
    RAW_BOLD = "\\033[1m"
    RAW_RESET = "\\033[0m"
    RAW_CYAN = "\\033[36m"
    RAW_GRAY = "\\033[90m"
    RAW_WHITE = "\\033[37m"

    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Assuming run.py is in src/infobim/run/
    # message_box.sh is in src/infobim/cli/
    msg_box_script = os.path.join(current_dir, "..", "cli", "message_box.sh")

    help_content = f"""
  {RAW_WHITE}Usage:{RAW_RESET}
    {RAW_GRAY}infobim run [OPTIONS]{RAW_RESET}

  {RAW_WHITE}Options:{RAW_RESET}
    {RAW_CYAN}--id <ID>{RAW_RESET}          {RAW_GRAY}Run specific capability by ID{RAW_RESET}
    {RAW_CYAN}--help, -h{RAW_RESET}         {RAW_GRAY}Show this help message{RAW_RESET}
    {RAW_CYAN}--root-path <PATH>{RAW_RESET} {RAW_GRAY}Set root path for repository{RAW_RESET}
    {RAW_CYAN}--limit <N>{RAW_RESET}        {RAW_GRAY}Limit number of results{RAW_RESET}
    {RAW_CYAN}--start <N>{RAW_RESET}        {RAW_GRAY}Start index for pagination{RAW_RESET}
    {RAW_CYAN}--file-name <PAT>{RAW_RESET}  {RAW_GRAY}Filter by file name pattern{RAW_RESET}
    {RAW_CYAN}--file-type <EXT>{RAW_RESET}  {RAW_GRAY}Filter by file type{RAW_RESET}
"""

    if os.path.exists(msg_box_script):
        import subprocess
        subprocess.run(["bash", msg_box_script, "GRAY", "InfoBIM", "Run Help", help_content], check=False)
    else:
        # Fallback to simple print if script is missing
        console = Console()
        console.print("Usage: infobim run [OPTIONS]", style="blue")
        print("")
        console.print("Options:", style="blue")
        print("  --id <ID>          Run specific capability by ID")
        print("  --help, -h         Show this help message")
        print("  --root-path <PATH> Set root path for repository")
        print("  --limit <N>        Limit number of results")
        print("  --start <N>        Start index for pagination")
        print("  --file-name <PAT>  Filter by file name pattern")
        print("  --file-type <EXT>  Filter by file type")
        print("")


def main():
    resolver: CliContextResolver = CliContextResolver()
    context: CliContextPort = resolver.resolve(sys.argv)

    if context.get_parameter_value("help"):
        show_help()
        sys.exit(0)

    # Check for unknown/unprocessed arguments
    if context.unprocessed_args:
        unknown_args = " ".join(context.unprocessed_args)
        print_message_box(
            YELLOW,
            "Warning",
            "Unknown Arguments",
            f"The following arguments were not recognized and will be ignored:\n\n{unknown_args}"
        )

    all_capabilities: List[type[Capability]] = get_all_capabilities()

    selected_capabilities: List[type[Capability]] = []
    for cap in all_capabilities:
        if resolver.is_satisfied_by(cap, context):
            if cap.METADATA.id not in [c.METADATA.id for c in selected_capabilities]:
                selected_capabilities.append(cap)

    if context.is_capability_targeted:
        target_id = context.parameters["capability_id"]["value"]
        
        # Check if the targeted capability exists in the full list
        target_cap = next((c for c in all_capabilities if c.METADATA.id == target_id), None)
        
        if not target_cap:
             print_message_box(
                RED,
                "Error",
                "Capability Not Found",
                f"Capability with ID {target_id} not found."
            )
             sys.exit(1)
             
        # Check if it was filtered out by satisfaction rules (optional, but good for validation)
        if target_id not in [c.METADATA.id for c in selected_capabilities]:
             pass
             
        run_capability(target_cap(), context)
        sys.exit(0)

    if not selected_capabilities:
        print_message_box(RED, "Error", f"Capability Discovery Error", "No capabilities found matching the criteria.")
        sys.exit(0)

    selector = SimpleMenuSelector()
    options = [
        {"label": f"{cap.METADATA.name} ({cap.METADATA.id})", "value": cap}
        for cap in selected_capabilities
    ]

    console = Console()

    print("")
    console.print(f"[bright_black]{FULL_HLINE}[/bright_black]")
    console.print(f"[cyan]Select Capability...[/cyan]")
    console.print(f"[bright_black]{FULL_HLINE}[/bright_black]")
    print("")

    def _select_capability_option(options):
        if not options:
            return None

        items = []
        for opt in options:
            cap = opt["value"]
            items.append(
                {
                    "name": cap.METADATA.name,
                    "id": cap.METADATA.id,
                    "value": cap,
                }
            )

        if not sys.stdin.isatty() or not sys.stdout.isatty():
            for idx, item in enumerate(items, 1):
                print(f"{idx}. {item['name']} ({item['id']})")
            try:
                answer = input("Select a capability [1..N] (Enter to cancel): ").strip()
            except EOFError:
                return None
            if not answer:
                return None
            if not answer.isdigit():
                return None
            choice = int(answer)
            if choice < 1 or choice > len(items):
                return None
            return items[choice - 1]["value"]

        import os
        import select
        import termios
        import tty

        cyan = "\033[36m"
        gray = "\033[90m"
        reset = "\033[0m"

        selected = 0
        menu_height = len(items) + 1

        def render() -> None:
            pointer = f"{cyan}➜{reset}"
            for i, item in enumerate(items):
                name = item["name"]
                cap_id = item["id"]
                if i == selected:
                    line = f"  {pointer} {cyan}{name}{reset} {gray}({cap_id}){reset}"
                else:
                    line = f"    {gray}{name} ({cap_id}){reset}"
                sys.stdout.write("\033[2K\r")
                sys.stdout.write(line + "\n")
            sys.stdout.write("\033[2K\r")
            sys.stdout.write(f"  {gray}Use ↑/↓ and Enter (Esc cancels){reset}\n")
            sys.stdout.flush()

        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            sys.stdout.write("\n")
            render()
            while True:
                ch = os.read(fd, 1)
                if ch in (b"\n", b"\r"):
                    return items[selected]["value"]
                if ch == b"\x1b":
                    r, _, _ = select.select([fd], [], [], 0.15)
                    if not r:
                        return None

                    prefix = os.read(fd, 1)
                    if prefix not in (b"[", b"O"):
                        return None

                    r, _, _ = select.select([fd], [], [], 0.15)
                    if not r:
                        return None

                    code = os.read(fd, 1)
                    if code == b"A":
                        selected = (selected - 1) % len(items)
                    elif code == b"B":
                        selected = (selected + 1) % len(items)
                    else:
                        return None

                    sys.stdout.write(f"\033[{menu_height}A")
                    render()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    selected_cap = _select_capability_option(options)
    
    if selected_cap:
        run_capability(selected_cap(), context)
    else:
        print("")
        log("INFO", "Exiting...")
        print("")

if __name__ == "__main__":
    main()
