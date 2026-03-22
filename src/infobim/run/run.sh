#!/bin/bash

clear
# Do not clear screen, let the user see previous output
# clear

# Get the script directory and root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

ORIGINAL_CWD=$(pwd)

cd "$ROOT_DIR" || exit 1

ENGINE="venv"
CONFIG_FILE=".__ontobdc__/config.yaml"
if [[ -f "$CONFIG_FILE" ]]; then
    ENGINE=$(awk '
        /^[[:space:]]*-[[:space:]]*install:/ { in_inst=1; next }
        /^[[:space:]]*-[[:space:]]*[^[:space:]]/ && in_inst { exit }
        in_inst && $1 ~ /engine:/ {
            for (i=2; i<=NF; i++) {
                printf "%s%s", $i, (i<NF?" ":"")
            }
            print ""
            exit
        }
    ' "$CONFIG_FILE")
    [[ -z "$ENGINE" ]] && ENGINE="venv"
fi

# Check if --root-path or --repository is already provided
HAS_ROOT_PATH=false
for arg in "$@"; do
    if [[ "$arg" == "--root-path" || "$arg" == "--repository" ]]; then
        HAS_ROOT_PATH=true
        break
    fi
done

if [ "$HAS_ROOT_PATH" = false ]; then
    # Inject --root-path with original CWD
    set -- "$@" "--root-path" "$ORIGINAL_CWD"
fi

if [ "$ENGINE" == "colab" ]; then
    # For colab, just run python
    exec python3 infobim/run/run.py "$@"
else
    # For local, use venv
    if [[ -n "$VIRTUAL_ENV" ]]; then
        # Already in a venv, do nothing
        :
    elif [[ -f "venv/bin/activate" ]]; then
        source venv/bin/activate
    elif [[ -f ".venv/bin/activate" ]]; then
        source .venv/bin/activate
    elif [[ -f "${ORIGINAL_CWD}/.venv/bin/activate" ]]; then
        source "${ORIGINAL_CWD}/.venv/bin/activate"
    elif [[ -f "${ORIGINAL_CWD}/venv/bin/activate" ]]; then
        source "${ORIGINAL_CWD}/venv/bin/activate"
    else
        echo "Virtual environment not found in venv/ or .venv/"
        echo "Please run 'infobim check --repair' to setup the environment."
        exit 1
    fi
    # Use python from path (which should be the venv python now)
    # And run module instead of file path to ensure imports work correctly
    exec python3 -m infobim.run.run "$@"
fi
