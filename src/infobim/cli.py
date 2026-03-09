import sys
import subprocess
import os
import importlib.resources


def main():
    # Try to find the infobim.sh script within the installed package
    try:
        # Use importlib.resources to find the file
        # For python >= 3.9
        if sys.version_info >= (3, 9):
            script_path = str(importlib.resources.files('infobim').joinpath('infobim.sh'))
        else:
            # Fallback for older versions (less likely in current context)
            with importlib.resources.path('infobim', 'infobim.sh') as p:
                script_path = str(p)
                
        if not os.path.exists(script_path):
             # Fallback for local development environment (editable install)
            script_path = os.path.join(os.path.dirname(__file__), 'infobim.sh')
    except Exception:
        # Generic fallback
        script_path = os.path.join(os.path.dirname(__file__), 'infobim.sh')

    # Ensure the script is executable
    if os.path.exists(script_path):
        os.chmod(script_path, 0o755)
        cmd = [script_path] + sys.argv[1:]
    else:
        # If script is not found, try running ontobdc directly (fallback)
        print(f"Warning: Script infobim.sh not found at {script_path}. Using ontobdc directly.", file=sys.stderr)
        cmd = ["ontobdc"] + sys.argv[1:]

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except FileNotFoundError:
        print(f"Error: Command '{cmd[0]}' not found.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
