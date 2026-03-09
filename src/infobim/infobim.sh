#!/bin/bash
# Wrapper to forward commands to ontobdc

# Find the python/ontobdc executable
if [ -f "$(pwd)/.venv/bin/ontobdc" ]; then
    ONTOBDC="$(pwd)/.venv/bin/ontobdc"
elif [ -f "$(dirname "$0")/../../../../.venv/bin/ontobdc" ]; then
    # Try relative path assuming script is in infobim/src/infobim
    ONTOBDC="$(dirname "$0")/../../../../.venv/bin/ontobdc"
else
    # Fallback to system path
    ONTOBDC="ontobdc"
fi

# ANSI colors
BOLD="\033[1m"
RESET="\033[0m"
GREEN="\033[32m"
CYAN="\033[36m"
GRAY='\033[90m'

# Custom help handler
if [[ "$1" == "--help" || "$1" == "-h" || -z "$1" ]]; then
    echo ""
    echo -e "${BOLD}InfoBIM CLI${RESET}"
    echo -e "  ${CYAN}check${RESET}     ${GRAY}Run infrastructure checks${RESET}"
    echo -e "  ${CYAN}setup${RESET}     ${GRAY}Create infobim config file with engine (venv|colab)${RESET}"
    echo -e "  ${CYAN}run${RESET}       ${GRAY}Run a capability via infobim run${RESET}"
    echo -e "  ${CYAN}plan${RESET}      ${GRAY}Plan capability execution${RESET}"
    echo ""
    exit 0
fi

# Intercept 'check' command to run InfoBIM's check.sh
if [[ "$1" == "check" ]]; then
    # Get the directory of this script
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    
    # Path to check.sh relative to this script
    # This script is in src/infobim/infobim.sh
    # check.sh is in src/infobim/check/check.sh
    CHECK_SCRIPT="${SCRIPT_DIR}/check/check.sh"
    
    if [ -f "$CHECK_SCRIPT" ]; then
        shift # Remove 'check' from args
        exec "$CHECK_SCRIPT" "$@"
    else
        # If check.sh is not found relative to this script, 
        # it might be because this script is running from the installed package
        # but check.sh wasn't included or paths are different.
        
        # Try to find check.sh using python resource location if available
        PYTHON_CHECK_SCRIPT=$(python3 -c "import infobim.check, os; print(os.path.join(os.path.dirname(infobim.check.__file__), 'check.sh'))" 2>/dev/null)
        
        if [ -f "$PYTHON_CHECK_SCRIPT" ]; then
             shift
             exec "$PYTHON_CHECK_SCRIPT" "$@"
        else
            echo "Error: InfoBIM check script not found at $CHECK_SCRIPT"
            # Fallback to ontobdc check if we really can't find ours
            # exec "$ONTOBDC" "check" "$@"
            exit 1
        fi
    fi
fi

exec "$ONTOBDC" "$@"
