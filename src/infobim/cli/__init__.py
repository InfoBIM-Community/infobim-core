
import os
import sys
import argparse
import subprocess
from infobim.run.run import main as run_main
from ontobdc.cli.init import log, message_box

try:
    from ontobdc.list.list import main as list_main
except ImportError:
    list_main = None


def check_main(args):
    # Get the directory of this file (src/ontobdc/cli)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Path to check.sh (src/ontobdc/check/check.sh)
    # cli/.. -> src/ontobdc -> check -> check.sh
    check_script = os.path.join(current_dir, "..", "check", "check.sh")
    
    if not os.path.exists(check_script):
        print(f"Error: check.sh not found at {check_script}")
        sys.exit(1)
        
    # Build command arguments
    cmd = [check_script]
    if args.repair:
        cmd.append("--repair")
    
    # Execute the shell script
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except Exception as e:
        print(f"Error executing check script: {e}")
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

    if cmd == "init":
        from infobim.cli.init import init_main
        init_main()
        sys.exit(0)

    else:
        # Check if engine is installed/initialized
        current_dir = os.path.dirname(os.path.abspath(__file__))
        is_engine_installed_script = os.path.join(current_dir, "..", "check", "infra", "is_engine_installed", "init.sh")
        if not os.path.exists(is_engine_installed_script):
            try:
                import ontobdc

                is_engine_installed_script = os.path.join(
                    os.path.dirname(ontobdc.__file__), "check", "infra", "is_engine_installed", "init.sh"
                )
            except Exception:
                pass

        if os.path.exists(is_engine_installed_script):
            check_cmd = f"source {is_engine_installed_script} && check"
            try:
                subprocess.run(check_cmd, shell=True, check=True, executable="/bin/bash", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except subprocess.CalledProcessError:
                message_box("RED", "Error", "Not Initialized", "InfoBIM is not initialized. Please run 'infobim init'.")
                sys.exit(1)
        else:
            message_box("RED", "Error", f"Fatal Error", "InfoBIM engine is not correctly installed. Please run 'pip uninstall infobim' and then 'pip install infobim' again.")
            sys.exit(1)

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
        parser = argparse.ArgumentParser(description="System Check")
        parser.add_argument("--repair", action="store_true", help="Attempt to repair issues")
        # Parse only arguments after 'check'
        args, unknown = parser.parse_known_args(sys.argv[2:])
        check_main(args)

    else:
        print("")
        subprocess.run(["bash", print_log_script, "ERROR", f"The '{cmd}' command was not found."], check=False)
        print("")
        print_help()
        sys.exit(1)
