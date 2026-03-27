
import os
import sys
import json
import yaml
import argparse
from ontobdc.cli.init import log, message_box


def init_main():
    """
    Initialize OntoBDC configuration.
    Creates .__ontobdc__ directory and config.yaml with specified engine.
    """
    parser = argparse.ArgumentParser(description="Initialize OntoBDC configuration")
    parser.add_argument("engine", nargs="?", help="Execution engine (e.g. venv, colab). If omitted, attempts auto-detection.")
    
    # We only parse arguments relevant to init
    args, unknown = parser.parse_known_args(sys.argv[2:])
    
    engine = args.engine

    # DRY: Automatic engine detection if not provided
    if not engine:
        # Check for Colab
        if os.path.exists("/content"):
            engine = "colab"
        # Check for Venv
        elif sys.prefix != sys.base_prefix:
            engine = "venv"
        else:
            message_box(
                "ERROR",
                "Error",
                "Engine not specified and could not be automatically detected (not in Colab or active Venv).",
                f"Please specify engine: ontobdc init <engine>",
            )
            sys.exit(1)

        log("INFO", f"Automatically detected engine: {engine}")

    # 1. Validate Engine against check/config.json
    # Locate config.json relative to this file
    print(os.getcwd())
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # cli/.. -> src/ontobdc -> check -> config.json
    config_json_path = os.path.join(current_dir, "..", "check", "config.json")

    valid_engines = []
    if os.path.exists(config_json_path):
        try:
            with open(config_json_path, 'r') as f:
                data = json.load(f)
                valid_engines = data.get('config', {}).get('engines', [])
        except Exception as e:
            message_box("ERROR", "Error", "JSON Validation Error", f"Failed to load config.json validation: {e}")
            return
    
    if valid_engines and engine not in valid_engines:
        message_box("ERROR", f"Invalid Engine '{engine}'.", f"Valid engines are: {', '.join(valid_engines)}")
        sys.exit(1)

    # 2. Create .__ontobdc__ directory in current working directory
    cwd = os.getcwd()
    ontobdc_dir = os.path.join(cwd, ".__ontobdc__")
    config_file = os.path.join(ontobdc_dir, "config.yaml")

    if os.path.exists(config_file):
        message_box("YELLOW", "Warning", "Already Initialized", "InfoBIM is already initialized in this directory.")
        return

    if not os.path.exists(ontobdc_dir):
        log("INFO", f"Creating directory {ontobdc_dir}...")
        os.makedirs(ontobdc_dir)
    else:
        log("DEBUG", f"Directory {ontobdc_dir} already exists.")

    # 3. Create/Update config.yaml
    config_data = {}
    if os.path.exists(config_file):
        log("INFO", f"Updating existing config at {config_file}...")
        try:
            with open(config_file, 'r') as f:
                config_data = yaml.safe_load(f) or {}
        except Exception:
            pass
    else:
        log("INFO", f"Creating new config file at {config_file}...")

    # Set engine
    config_data['engine'] = engine

    try:
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False)

        log("SUCCESS", f"Engine set to '{engine}'", f"path={config_file}")
    except Exception as e:
        message_box("ERROR", "Error", f"Error writing config file: {e}")
        sys.exit(1)

    # 4. Run Check Repair (optional but recommended)
    # We delegate to check command
    print("")
    from infobim.cli import check_main
        
    try:
        check_main()
    except SystemExit:
        # check_main calls sys.exit, we catch it to not crash if check fails but init succeeded
        pass






