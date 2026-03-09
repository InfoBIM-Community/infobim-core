#!/bin/bash

# Get the directory where the script is located
INFOBIM_CHECK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# When installed via pip, the structure is flat inside site-packages/ontobdc
# INFOBIM_CHECK_DIR is .../ontobdc/check
# MODULE_ROOT is .../ontobdc
MODULE_ROOT="$(cd "${INFOBIM_CHECK_DIR}/.." && pwd)"

# Try to find message_box.sh in likely locations
# 1. In project root (development mode): .../src/ontobdc/../../message_box.sh -> src/../message_box.sh (ontobdc-wip/message_box.sh)
# 2. In installed package root: .../site-packages/ontobdc/message_box.sh

# Find ontobdc message_box
if [ -f "${MODULE_ROOT}/../../message_box.sh" ]; then
    MESSAGE_BOX="${MODULE_ROOT}/../../message_box.sh"
elif [ -f "${MODULE_ROOT}/message_box.sh" ]; then
    MESSAGE_BOX="${MODULE_ROOT}/message_box.sh"
else
    # Try finding via python
    MESSAGE_BOX=$(python3 -c "import ontobdc, os; print(os.path.join(os.path.dirname(ontobdc.__file__), 'message_box.sh'))" 2>/dev/null)
fi

# Define paths
CONFIG_JSON="${INFOBIM_CHECK_DIR}/config.json"

if [ -f "${MESSAGE_BOX}" ]; then
    source "${MESSAGE_BOX}"
else
    # Fallback if message_box is missing
    print_message_box() {
        echo "[$1] $2: $3"
        echo -e "$4"
    }
    # Define colors if not sourced
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    CYAN='\033[0;36m'
    GRAY='\033[0;90m'
    WHITE='\033[1;37m'
    RESET='\033[0m'
    FULL_HLINE="----------------------------------------"
fi

REPAIR_MODE=false
SCOPE="all"

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --repair) REPAIR_MODE=true ;;
        --scope) SCOPE="$2"; shift ;;
        *) ;;
    esac
    shift
done

echo ""
echo -e "${GRAY}${FULL_HLINE}${RESET}"
echo -e "${CYAN}Running InfoBIM System Checks...${RESET}"
echo -e "${GRAY}${FULL_HLINE}${RESET}"
echo ""

# Activate Venv if not active (crucial for checks that rely on venv)
if [ -z "$VIRTUAL_ENV" ]; then
    # Try to find venv relative to INFOBIM_CHECK_DIR or CWD
    # Assuming standard structure: infobim-stack/.venv
    # INFOBIM_CHECK_DIR is .../infobim/src/infobim/check
    # Try relative to script location first
    POTENTIAL_VENV_1="$(cd "${INFOBIM_CHECK_DIR}/../../../../../.venv" 2>/dev/null && pwd)/bin/activate"
    # Try relative to current working directory
    POTENTIAL_VENV_2="$(pwd)/.venv/bin/activate"
    
    if [ -f "$POTENTIAL_VENV_1" ]; then
        source "$POTENTIAL_VENV_1"
    elif [ -f "$POTENTIAL_VENV_2" ]; then
        source "$POTENTIAL_VENV_2"
    fi
fi

# Ensure VIRTUAL_ENV is exported if we sourced it
if [ -z "$VIRTUAL_ENV" ]; then
    # Check if we are running via a python that is inside a venv (common when calling script from wrapper)
    PYTHON_BIN=$(which python3)
    if [[ "$PYTHON_BIN" == *".venv"* || "$PYTHON_BIN" == *"venv"* ]]; then
        # Reconstruct VIRTUAL_ENV path
        export VIRTUAL_ENV="${PYTHON_BIN%/bin/python3}"
        # Update PATH to ensure venv bin is first
        export PATH="$VIRTUAL_ENV/bin:$PATH"
    fi
fi

ERRORS=()
WARNINGS=()

run_checks() {
    local DIR="$1"
    local NAME="$2"
    local ENGINE="$3"
    local CFG="$4"
    
    echo -e "${YELLOW}❯ ${WHITE}Checking ${CYAN}${NAME}${RESET}"
    
    if [ ! -f "$CFG" ]; then
         echo -e "  ${RED}✗ Config file not found: ${CFG}${RESET}"
         ERRORS+=("Config file missing for $NAME")
         return
    fi

    # Parse JSON using python
    # Get base checks
    BASE_CHECKS=$(python3 -c "import json; import sys; 
try:
    with open('$CFG') as f: data = json.load(f);
    print(' '.join(data.get('base', {}).get('$NAME', [])))
except Exception as e: print(e, file=sys.stderr)")

    # Get engine specific checks
    ENGINE_CHECKS=$(python3 -c "import json; import sys; 
try:
    with open('$CFG') as f: data = json.load(f);
    print(' '.join(data.get('engines', {}).get('$ENGINE', {}).get('$NAME', [])))
except Exception as e: print(e, file=sys.stderr)")

    CHECKS="$BASE_CHECKS $ENGINE_CHECKS"
    
    if [ -z "$CHECKS" ] || [ "$CHECKS" == " " ]; then
        echo -e "  ${GRAY}• No checks found for $NAME in $ENGINE${RESET}"
        return
    fi

    for check_name in $CHECKS; do
        # Check script path: dir/check_name/init.sh
        check_script="$DIR/$check_name/init.sh"
        
        if [ -f "$check_script" ]; then
            DESCRIPTION=""
            unset -f check
            unset -f repair
            unset -f hotfix
            
            # shellcheck disable=SC1090
            source "$check_script"
            
            # Default description if missing
            if [ -z "$DESCRIPTION" ]; then
                DESCRIPTION="$check_name"
            fi

            check
            RET_CODE=$?

            if [ $RET_CODE -eq 0 ]; then
                 echo -e "  ${GREEN}✓ ${DESCRIPTION}${RESET}"
            else
                 # If return code is 2, it's a fatal error
                 IS_FATAL=false
                 if [ $RET_CODE -eq 2 ]; then
                    IS_FATAL=true
                 fi

                 HOTFIXED=false
                 if type hotfix &>/dev/null; then
                     if hotfix; then
                         if check; then
                             echo -e "  ${GREEN}✓ ${DESCRIPTION} (Hotfixed)${RESET}"
                             WARNINGS+=("${DESCRIPTION} (Hotfixed)")
                             HOTFIXED=true
                         fi
                     fi
                 fi

                 if [ "$HOTFIXED" = false ]; then
                     if [ "$IS_FATAL" = true ]; then
                         echo -e "  ${RED}✗ ${DESCRIPTION} (FATAL)${RESET}"
                         if type repair &>/dev/null; then
                             repair
                         else
                             echo -e "${RED}FATAL ERROR: ${DESCRIPTION} failed and no repair available.${RESET}"
                             exit 1
                         fi
                     fi

                     if [ "$REPAIR_MODE" = true ]; then
                         echo -e "  ${YELLOW}⚡ Attempting repair for: ${DESCRIPTION}...${RESET}"
                         if type repair &>/dev/null; then
                             repair
                             
                             check
                             if [ $? -eq 0 ]; then
                                 echo -e "  ${GREEN}✓ ${DESCRIPTION} (Repaired)${RESET}"
                                 WARNINGS+=("${DESCRIPTION} (Repaired)")
                             else
                                 echo -e "  ${RED}✗ ${DESCRIPTION} (Repair failed)${RESET}"
                                 ERRORS+=("${DESCRIPTION}")
                             fi
                         else
                             echo -e "  ${RED}✗ ${DESCRIPTION} (No repair function)${RESET}"
                             ERRORS+=("${DESCRIPTION}")
                         fi
                     else
                         echo -e "  ${RED}✗ ${DESCRIPTION}${RESET}"
                         ERRORS+=("${DESCRIPTION}")
                     fi
                 fi
            fi
        else
             echo -e "  ${GRAY}• Check script not found: $check_script${RESET}"
        fi
    done
}

# Determine Engine
ENGINE="venv"
# Heuristic for colab
if [ -d "/content" ]; then
    ENGINE="colab"
fi

# Run OntoBDC Checks
ONTOBDC_DIR=$(python3 -c "import ontobdc, os; print(os.path.dirname(ontobdc.__file__))" 2>/dev/null)
if [ -n "$ONTOBDC_DIR" ] && [ -d "$ONTOBDC_DIR/check" ]; then
    ONTOBDC_CHECK_DIR="$ONTOBDC_DIR/check"
    ONTOBDC_CONFIG="$ONTOBDC_CHECK_DIR/config.json"
    
    if [[ "$SCOPE" == "all" || "$SCOPE" == "infra" ]]; then
        INFRA_DIR="${ONTOBDC_CHECK_DIR}/infra"
        if [[ -d "${INFRA_DIR}" ]]; then
            run_checks "${INFRA_DIR}" "infra" "$ENGINE" "$ONTOBDC_CONFIG"
        fi
    fi
else
    echo -e "${YELLOW}Warning: OntoBDC check directory not found.${RESET}"
fi

# Run InfoBIM Checks
if [[ "$SCOPE" == "all" || "$SCOPE" == "infra" ]]; then
    # Correct path to infra checks for infobim
    INFRA_DIR="${INFOBIM_CHECK_DIR}/infra"
    
    if [[ -d "${INFRA_DIR}" ]]; then
        run_checks "${INFRA_DIR}" "infra" "$ENGINE" "$CONFIG_JSON"
    else 
         echo -e "${RED}Error: InfoBIM infra directory not found: ${INFRA_DIR}${RESET}"
    fi
fi

if [ -z "$VIRTUAL_ENV" ] && [ -f "venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source "venv/bin/activate"
fi

echo ""

if [ ${#ERRORS[@]} -eq 0 ]; then
    MSG="All checks passed."
    if [ ${#WARNINGS[@]} -gt 0 ]; then
        MSG="${MSG}\n\nWarnings:"
        for w in "${WARNINGS[@]}"; do
            MSG="${MSG}\n• $w"
        done
    fi
    if type print_message_box &>/dev/null; then
        print_message_box "$GREEN" "Success" "System Operational" "$MSG"
    else
        echo -e "${GREEN}Success: System Operational${RESET}\n$MSG"
    fi
else
    MSG="The following checks failed:"
    for e in "${ERRORS[@]}"; do
        MSG="${MSG}\n• $e"
    done
    
    if [ ${#WARNINGS[@]} -gt 0 ]; then
        MSG="${MSG}\n\nWarnings:"
        for w in "${WARNINGS[@]}"; do
            MSG="${MSG}\n• $w"
        done
    fi
    
    if type print_message_box &>/dev/null; then
        print_message_box "$RED" "Error" "System Check Failed" "$MSG"
    else
        echo -e "${RED}Error: System Check Failed${RESET}\n$MSG"
    fi
    # Exit with error code if there were errors
    exit 1
fi

echo ""
exit 0
