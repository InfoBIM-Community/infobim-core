#!/bin/bash

DESCRIPTION="InfoBIM Python Dependencies"

check() {
    # Check if we are inside a virtual environment
    if [ -z "$VIRTUAL_ENV" ]; then
        echo "Not in a virtual environment."
        return 2
    fi
    
    # Check if infobim package is installed (editable or not)
    if ! pip show infobim &> /dev/null; then
        echo "InfoBIM package not installed."
        return 1
    fi
    
    return 0
}

repair() {
    echo "Installing InfoBIM dependencies..."
    
    # Get the project root
    # SCRIPT_DIR is .../infobim/src/infobim/check/infra/install_python_dependencies
    # ROOT is .../infobim
    local SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../../../../" && pwd)"
    
    if [ -f "${PROJECT_ROOT}/pyproject.toml" ]; then
        pip install -e "${PROJECT_ROOT}"
    else
        echo "Could not find pyproject.toml at ${PROJECT_ROOT}"
        return 1
    fi
}
