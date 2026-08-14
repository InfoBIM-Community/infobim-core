#!/bin/bash

MODULE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${MODULE_DIR}/../.." && pwd)"

cd "$ROOT_DIR" || exit 1

BOLD='\033[1m'
RESET='\033[0m'
CYAN='\033[36m'
GRAY='\033[90m'
WHITE='\033[37m'
YELLOW='\033[33m'
GREEN='\033[32m'
RED='\033[31m'
BLUE='\033[34m'
REVERSE='\033[7m'

TERM_WIDTH=$(tput cols)
INNER_WIDTH=$((TERM_WIDTH - 2))

HLINE=$(printf '─%.0s' $(seq 1 $INNER_WIDTH))
FULL_HLINE=$(printf '─%.0s' $(seq 1 $TERM_WIDTH))

source "${ROOT_DIR}/stack/message_box.sh"

ENGINE="venv"
CONFIG_FILE="config/infobim.yaml"
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

if [ "$ENGINE" != "colab" ]; then
    if [[ -f "venv/bin/activate" ]]; then
        source venv/bin/activate
    else
        echo -e "${RED}Virtual environment not found in venv/${RESET}"
        echo -e "${YELLOW}Please run './infobim check --repair' to setup the environment.${RESET}"
        exit 1
    fi
else
    deactivate() {
        :
    }
fi

REPAIR_MODE=false
if [[ "$1" == "scan" ]]; then
    shift
fi

if [[ "$1" == "--repair" ]]; then
    REPAIR_MODE=true
fi

CONFIG_MODE=false
if [[ "$1" == "--config" ]]; then
    CONFIG_MODE=true
fi

if [ "$CONFIG_MODE" = false ]; then
    echo ""
    echo -e "${GRAY}${FULL_HLINE}${RESET}"
    echo -e "${CYAN}Running IFC Checks...${RESET}"
    echo -e "${GRAY}${FULL_HLINE}${RESET}"
    echo ""

    CHECK_DIR="stack/check/ifc"
    ANY_CHECK_FAILED=false

    if [ ! -d "$CHECK_DIR" ]; then
        echo -e "${RED}Directory not found: ${CHECK_DIR}${RESET}"
        deactivate
        exit 1
    fi

    for check_script in "$CHECK_DIR"/*.sh; do
        if [ -f "$check_script" ]; then
            DESCRIPTION=""
            unset -f check
            unset -f repair
            unset -f hotfix

            source "$check_script"

            if check; then
                echo -e "  ${GREEN}✓ ${DESCRIPTION}${RESET}"
            else
                HOTFIXED=false
                if type hotfix &>/dev/null; then
                    if hotfix; then
                        if check; then
                            echo -e "  ${GREEN}✓ ${DESCRIPTION} (Hotfixed)${RESET}"
                            HOTFIXED=true
                        fi
                    fi
                fi

                if [ "$HOTFIXED" = false ]; then
                    if [ "$REPAIR_MODE" = true ]; then
                        echo -e "  ${YELLOW}⚡ Attempting repair for: ${DESCRIPTION}...${RESET}"
                        if type repair &>/dev/null; then
                            repair
                            if check; then
                                echo -e "  ${GREEN}✓ ${DESCRIPTION} (Repaired)${RESET}"
                            else
                                echo -e "  ${RED}✗ ${DESCRIPTION} (Repair failed)${RESET}"
                                ANY_CHECK_FAILED=true
                            fi
                        else
                            echo -e "  ${RED}✗ ${DESCRIPTION} (No repair function)${RESET}"
                            ANY_CHECK_FAILED=true
                        fi
                    else
                        echo -e "  ${RED}✗ ${DESCRIPTION}${RESET}"
                        if type repair &>/dev/null; then
                            repair
                        fi
                        ANY_CHECK_FAILED=true
                    fi
                fi
            fi
        fi
    done

    if [ "$ANY_CHECK_FAILED" = true ]; then
        echo ""
        print_message_box "RED" "Error" "Checks Failed" "One or more checks failed.\n\n Please run ${CYAN}'./infobim check --repair'${GRAY} to fix the issues.${RESET}"
        echo ""
        deactivate
        exit 1
    fi
fi

if [ "$CONFIG_MODE" = true ]; then
    echo ""
    echo -e "${GRAY}${FULL_HLINE}${RESET}"
    echo -e "${CYAN}Starting IFC Configuration...${RESET}"
    echo -e "${GRAY}${FULL_HLINE}${RESET}"
    echo ""

    get_config_value() {
        local key="$1"
        local default="$2"
        local config_file="stack/infobim-ifc.yaml"

        if [ ! -f "$config_file" ]; then
            echo "$default"
            return
        fi

        python3 -c "
import yaml, sys
try:
    with open('$config_file', 'r') as f:
        config = yaml.safe_load(f) or {}
    keys = '$key'.split('.')
    val = config
    for k in keys:
        val = val.get(k, {})
    if isinstance(val, dict) and not val:
        print('$default')
    elif val is None:
        print('$default')
    else:
        print(val)
except:
    print('$default')
"
    }

    CURRENT_ENGINE=$(get_config_value "engine.ifc" "")
    if [ -n "$CURRENT_ENGINE" ] && [ "$CURRENT_ENGINE" != "unknown" ]; then
        echo ""
        print_message_box "BLUE" "Info" "Configuration" "Current engine is set to: $CURRENT_ENGINE"
        echo ""
        echo -e "${YELLOW}Do you want to reconfigure the IFC engine? [y/N] ${RESET}\c"
        read -r response
        if [[ ! "$response" =~ ^[yY][eE][sS]|[yY]$ ]]; then
            echo ""
            echo "Exiting..."
            exit 0
        fi
    fi

    export PYTHONPATH=$PYTHONPATH:.
    python3 "./stack/src/tui/terminal/ifc.py" "$@"

else
    echo ""
    echo -e "${GRAY}${FULL_HLINE}${RESET}"
    echo -e "${CYAN}Starting IFC TUI...${RESET}"
    echo -e "${GRAY}${FULL_HLINE}${RESET}"
    echo ""

    get_config_value() {
        local key="$1"
        local default="$2"
        local config_file="stack/infobim-ifc.yaml"

        if [ ! -f "$config_file" ]; then
            echo "$default"
            return
        fi

        python3 -c "
import yaml, sys
try:
    with open('$config_file', 'r') as f:
        config = yaml.safe_load(f) or {}
    keys = '$key'.split('.')
    val = config
    for k in keys:
        val = val.get(k, {})
    if isinstance(val, dict) and not val:
        print('$default')
    elif val is None:
        print('$default')
    else:
        print(val)
except:
    print('$default')
"
    }

    CURRENT_ENGINE=$(get_config_value "engine.ifc" "unknown")

    if [ "$CURRENT_ENGINE" == "docker" ]; then
        echo -e "${CYAN}Infobim is configured to run locally via Docker.${RESET}"

        if [ -z "$DOCKER_COMPOSE_CMD" ] || [ -z "$COMPOSE_FILE" ]; then
            echo -e "${RED}Error: Docker environment variables missing. Please run './infobim check'${RESET}"
            exit 1
        fi

        echo ""
        echo -e "${CYAN}Starting container for environment: ${ENVIRONMENT}...${RESET}"
        echo ""

        $DOCKER_COMPOSE_CMD -f "$COMPOSE_FILE" up -d

        if [ $? -ne 0 ]; then
            echo ""
            print_message_box "RED" "Error" "Container Startup Failed" "Failed to start Docker container."
            echo ""
            deactivate
            exit 1
        fi

        echo ""
        echo -e "${CYAN}Running TUI in container...${RESET}"
        echo ""
        $DOCKER_COMPOSE_CMD -f "$COMPOSE_FILE" exec infobim-tui python3 /app/stack/src/tui/terminal/ifc.py "$@"

        echo ""
        echo -e "${CYAN}Stopping container...${RESET}"
        $DOCKER_COMPOSE_CMD -f "$COMPOSE_FILE" stop

    else
        export PYTHONPATH=$PYTHONPATH:.
        python3 "./stack/src/tui/terminal/ifc.py" "$@"
    fi
fi

deactivate
