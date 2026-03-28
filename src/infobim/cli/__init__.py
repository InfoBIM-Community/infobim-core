
import os
import sys
import json
import argparse
import subprocess
from typing import Any, Dict
from infobim.run.run import main as run_main
from ontobdc.cli.init import log, message_box

try:
    from ontobdc.list.list import main as list_main
except ImportError:
    list_main = None


def get_script_dir() -> str:
    """
    Get the module root directory (infobim/).
    """
    try:
        import infobim
        if hasattr(infobim, '__path__'):
            package_path = infobim.__path__[0]
            return package_path
    except Exception:
        pass

    try:
        # pip show infobim | grep Location
        location = subprocess.check_output(["pip", "show", "infobim", "|", "grep", "Location"]).decode("utf-8").split(":")[1].strip()
        if location:
            return os.path.join(location, "infobim")
    except Exception:
        pass

    script_dir = os.path.dirname(os.path.abspath(__file__))
    module_root = os.path.abspath(os.path.join(script_dir, ".."))

    return module_root


def check_main(silent: bool = True):
    # Get the directory of this file (src/ontobdc/cli)
    from ontobdc.cli import get_root_dir
    root_dir: str = get_root_dir()
    if not root_dir:
        message_box("ERROR", "Error", "Config Error", "Failed to find ontobdc_dir in config.yaml.")
        sys.exit(1)

    ontobdc_dir: str = os.path.join(root_dir, ".__ontobdc__")
    if not os.path.exists(ontobdc_dir):
        message_box("ERROR", "Error", "Config Error", f"Failed to find ontobdc_dir in {root_dir}.")
        sys.exit(1)

    script_dir: str = get_script_dir()
    if not script_dir:
        message_box("ERROR", "Error", "Config Error", "Failed to find script_dir in config.yaml.")
        sys.exit(1)

    config_file = os.path.join(script_dir, "check", "config.json")
    if not os.path.exists(config_file):
        message_box("ERROR", "Error", "Config Error", f"Failed to find config.json in {script_dir}.")
        sys.exit(1)

    try:
        with open(config_file, 'r') as f:
            data = json.load(f)
    except Exception as e:
        message_box("ERROR", "Error", "JSON Validation Error", f"Failed to load config.json validation: {e}")
        sys.exit(1)

    valid_engines: Dict[str, Any] = {
        "script_path": data.get('script_path', {}),
        "base": data.get('base', {}),
        "infobim": data.get('infobim', {}),
        "engine": data.get('engine', {})
    }

    valid_engines["script_path"]["alternative"] = os.path.join(script_dir, "check")

    check_file = os.path.join(ontobdc_dir, "check.json")
    try:
        os.makedirs(ontobdc_dir, exist_ok=True)
        with open(check_file, "w") as f:
            json.dump(valid_engines, f, indent=2)
    except Exception as e:
        message_box("ERROR", "Error", "JSON Write Error", f"Failed to write check.json: {e}")
        sys.exit(1)

    # Execute the shell script
    cmd = ['ontobdc', 'check', '--repair']

    try:
        if silent:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(cmd, check=True)

    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except Exception as e:
        message_box("ERROR", "Error", "Execution Error", f"Failed to execute check script: {e}")
        sys.exit(1)


def print_help():
    # Colors
    BOLD = '\033[1m'
    RESET = '\033[0m'
    CYAN = '\033[36m'
    GRAY = '\033[90m'
    WHITE = '\033[37m'

    help_content = f"""
  {WHITE}Usage:{RESET}
    {GRAY}infobim{RESET} {CYAN}<command>{RESET} {GRAY}[flags/parameters]{RESET}

  {WHITE}Commands:{RESET}
    {CYAN}init{RESET}      {GRAY}Initialize infobim config with engine (venv|colab){RESET}
    {CYAN}check{RESET}     {GRAY}Run infrastructure checks{RESET}
    {CYAN}run{RESET}       {GRAY}Run a capability via infobim/run{RESET}
    {CYAN}list{RESET}      {GRAY}List all available capabilities{RESET}
"""

    message_box("GRAY", "InfoBIM", "CLI Help", help_content)


def main():
    # If no args, print help
    if len(sys.argv) == 1:
        print_help()
        sys.exit(0)

    cmd = sys.argv[1]
    
    if cmd in ["-h", "--help", "help"]:
        print_help()
        sys.exit(0)

    if cmd in ["-v", "--version", "version"]:
        try:
            from importlib.metadata import version
            ver = version("infobim")
        except Exception:
            ver = "unknown"

        message_box("BLUE", "InfoBIM", f"Version: {ver}", "The Capability Engine for BIM Automation")
        sys.exit(0)

    try:
        import ontobdc

        print_log_script = os.path.join(os.path.dirname(ontobdc.__file__), "cli", "print_log.sh")
    except Exception:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        print_log_script = os.path.join(current_dir, "print_log.sh")

    from ontobdc.cli import config_data as get_config_data
    from typing import Dict, Any
    print('')

    config_data: Dict[str, Any] = get_config_data()
    if not config_data:
        subprocess.run(
            ["bash", print_log_script, "WARN", "InfoBIM config data is not correctly installed. Trying to auto-repair..."],
            check=False,
        )

        from infobim.cli.init import init_main
        init_main()
        sys.exit(0)

    check_main()

    if cmd == "run":
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        run_main()
        
    elif cmd == "list":
        if list_main:
            sys.argv = [sys.argv[0]] + sys.argv[2:]
            list_main()
        else:
            message_box("RED", "Error", "Fatal Error", "InfoBIM list module is not correctly installed.")
            sys.exit(1)

    elif cmd == "check":
        check_main(silent=False)

    else:
        print("")
        subprocess.run(["bash", print_log_script, "ERROR", f"The '{cmd}' command was not found."], check=False)
        print("")
        print_help()
        sys.exit(1)
