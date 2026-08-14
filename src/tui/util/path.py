import os
import yaml

def get_stack_root() -> str:
    """Returns the absolute path to the 'stack' directory."""
    # This file is at stack/src/util/path.py
    # stack root is at stack/
    # .. -> stack/src
    # .. -> stack
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

def get_message_box_script() -> str:
    """Returns the absolute path to the message_box.sh script."""
    return os.path.join(get_stack_root(), "message_box.sh")

def get_config_path():
    return os.path.abspath(os.path.join(get_stack_root(), "infobim-ifc.yaml"))

def get_project_root() -> str:
    """Returns the absolute path to the project root (parent of stack)."""
    return os.path.abspath(os.path.join(get_stack_root(), ".."))

def get_user_config_path():
    return os.path.join(get_project_root(), "data", "config.yaml")

def _merge_dicts(base, override):
    """Recursively merges override into base."""
    if not isinstance(override, dict):
        return override
    
    result = base.copy() if isinstance(base, dict) else {}
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_dicts(result[key], value)
        else:
            result[key] = value
    return result

def load_config():
    # 1. Load Base Config
    config_path = get_config_path()
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found at {config_path}")
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f) or {}

    # 2. Load User Config (data/config.yaml)
    user_path = get_user_config_path()
    if os.path.exists(user_path):
        try:
            with open(user_path, 'r') as f:
                user_config = yaml.safe_load(f) or {}
                config = _merge_dicts(config, user_config)
        except Exception as e:
            print(f"Warning: Failed to load user config: {e}")
            
    return config
