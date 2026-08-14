#!/bin/bash

BOLD='\033[1m'
RESET='\033[0m'
CYAN='\033[36m'
GRAY='\033[90m'
WHITE='\033[37m'
BLUE='\033[34m'
RED='\033[31m'

SCRIPT_PATH="${BASH_SOURCE[0]}"
while [ -h "$SCRIPT_PATH" ]; do
    DIR="$(cd -P "$(dirname "$SCRIPT_PATH")" && pwd)"
    TARGET="$(readlink "$SCRIPT_PATH")"
    case "$TARGET" in
        /*) SCRIPT_PATH="$TARGET" ;;
        *) SCRIPT_PATH="$DIR/$TARGET" ;;
    esac
done
SCRIPT_DIR="$(cd -P "$(dirname "$SCRIPT_PATH")" && pwd)"
CLI_DIR="${SCRIPT_DIR}/cli"
CONFIG_FILE="${SCRIPT_DIR}/../config/infobim.yaml"

if [[ "$1" == "-h" || "$1" == "--help" || "$1" == "help" ]]; then
    if [[ -f "${CLI_DIR}/help.sh" ]]; then
        bash "${CLI_DIR}/help.sh"
        exit 0
    fi
fi

if [[ "$1" == "install" ]]; then
    if [[ -f "${CLI_DIR}/install.sh" ]]; then
        shift
        bash "${CLI_DIR}/install.sh" "$@"
        exit $?
    fi
fi

if [[ "$1" == "check" ]]; then
    if [[ -f "${CLI_DIR}/check.sh" ]]; then
        shift
        bash "${CLI_DIR}/check.sh" "$@"
        exit $?
    fi
fi

if [[ "$1" == "ifc" ]]; then
    IFC_SOURCE=""
    if [[ -f "$CONFIG_FILE" ]]; then
        IFC_SOURCE=$(awk '
            /^[[:space:]]*-[[:space:]]*ifc:/ { in_mod=1; next }
            /^[[:space:]]*-[[:space:]]*[^[:space:]]/ && in_mod { exit }
            in_mod && $1 ~ /source:/ {
                sub(/.*source:[[:space:]]*/, "", $0);
                print $0;
                exit
            }
        ' "$CONFIG_FILE")
    fi

    if [[ -z "$IFC_SOURCE" ]]; then
        IFC_SOURCE="stack/ifc"
    fi

    IFC_SCRIPT="${SCRIPT_DIR}/../${IFC_SOURCE}/ifc.sh"
    if [[ -f "$IFC_SCRIPT" ]]; then
        shift
        bash "$IFC_SCRIPT" "$@"
        exit $?
    else
        echo -e "${RED}Error:${RESET} ifc.sh not found in module path: ${IFC_SOURCE}"
        exit 1
    fi
fi

if [[ "$1" == "run" || "$1" == "plan" ]]; then
    ACTION="$1"
    ONTOBDC_SCRIPT="${SCRIPT_DIR}/../ontobdc/ontobdc.sh"

    if [[ -f "$ONTOBDC_SCRIPT" ]]; then
        shift
        bash "$ONTOBDC_SCRIPT" "$ACTION" "$@"
        exit $?
    else
        echo -e "${RED}Error:${RESET} ontobdc.sh not found in module path."
        exit 1
    fi
fi

if [[ "$1" == "commit" || "$1" == "branch" ]]; then
    ACTION="$1"
    ONTOBDC_SCRIPT="${SCRIPT_DIR}/../ontobdc/ontobdc.sh"

    if [[ -f "$ONTOBDC_SCRIPT" ]]; then
        shift
        bash "$ONTOBDC_SCRIPT" "$ACTION" "$@"
        exit $?
    else
        echo -e "${RED}Error:${RESET} ontobdc.sh not found in module path."
        exit 1
    fi
fi

MODULE="$1"
if [[ -n "$MODULE" && "$MODULE" != "-h" && "$MODULE" != "--help" ]]; then
    if [[ -f "$CONFIG_FILE" ]] && grep -qE "^[[:space:]]*-[[:space:]]*${MODULE}:" "$CONFIG_FILE"; then
        MODULE_SCRIPT="${CLI_DIR}/${MODULE}.sh"
        if [[ -f "$MODULE_SCRIPT" ]]; then
            shift
            bash "$MODULE_SCRIPT" "$@"
            exit $?
        else
            echo -e "${RED}Error:${RESET} module '${MODULE}' is configured but ${CLI_DIR}/${MODULE}.sh was not found."
            exit 1
        fi
    else
        echo -e "${RED}Error:${RESET} unknown module '${MODULE}'."
        echo -e "${GRAY}Use ./infobim -h to list available commands.${RESET}"
        exit 1
    fi
fi

TERM_WIDTH=$(tput cols)
INNER_WIDTH=$((TERM_WIDTH - 2))

HLINE=$(printf '─%.0s' $(seq 1 $INNER_WIDTH))
FULL_HLINE=$(printf '─%.0s' $(seq 1 $TERM_WIDTH))

clear

print_box() {
    TITLE_VISIBLE_LEN=20
    TITLE_PAD_LEN=$((INNER_WIDTH - TITLE_VISIBLE_LEN))
    if [ $TITLE_PAD_LEN -lt 0 ]; then TITLE_PAD_LEN=0; fi
    TITLE_PAD=$(printf '%*s' "$TITLE_PAD_LEN" "")

    DIR_LABEL_LEN=12
    DIR=$(pwd | sed "s|$HOME|~|")
    MAX_DIR_LEN=$((INNER_WIDTH - DIR_LABEL_LEN))
    if [ ${#DIR} -gt $MAX_DIR_LEN ]; then
        DIR="${DIR:0:$((MAX_DIR_LEN-3))}..."
    fi

    DIR_FULL_LEN=$((DIR_LABEL_LEN + ${#DIR}))
    DIR_PAD_LEN=$((INNER_WIDTH - DIR_FULL_LEN))
    if [ $DIR_PAD_LEN -lt 0 ]; then DIR_PAD_LEN=0; fi
    DIR_PAD=$(printf '%*s' "$DIR_PAD_LEN" "")

    EMPTY_PAD=$(printf '%*s' "$INNER_WIDTH" "")

    echo "╭${HLINE}╮"
    echo -e "│ >_ ${BLUE}${BOLD}InfoBIM${RESET} (v0.1.0)${TITLE_PAD}│"
    echo "│${EMPTY_PAD}│"
    echo -e "│ ${GRAY}directory:${RESET} ${DIR}${DIR_PAD}│"

    if git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
        BRANCH=$(git branch --show-current 2>/dev/null || git rev-parse --abbrev-ref HEAD)
        BRANCH_LABEL_LEN=12
        MAX_BRANCH_LEN=$((INNER_WIDTH - BRANCH_LABEL_LEN))
        if [ ${#BRANCH} -gt $MAX_BRANCH_LEN ]; then
            BRANCH="${BRANCH:0:$((MAX_BRANCH_LEN-3))}..."
        fi
        BRANCH_FULL_LEN=$((BRANCH_LABEL_LEN + ${#BRANCH}))
        BRANCH_PAD_LEN=$((INNER_WIDTH - BRANCH_FULL_LEN))
        if [ $BRANCH_PAD_LEN -lt 0 ]; then BRANCH_PAD_LEN=0; fi
        BRANCH_PAD=$(printf '%*s' "$BRANCH_PAD_LEN" "")
        echo -e "│ ${GRAY}branch:${RESET}    ${BRANCH}${BRANCH_PAD}│"
    fi

    echo "╰${HLINE}╯"
}

print_slogan() {
    echo ""
    echo -e "  ${GRAY}BIM on the inside, drawings on the outside, data for everyone.${RESET}"
}

print_box
print_slogan

echo -e "${GRAY}${FULL_HLINE}${RESET}"
echo ""

echo ""
echo -e "  ${WHITE}Available commands:${RESET}"
echo -e "    ${CYAN}ifc${RESET}     ${GRAY}Tools for visualizing and inspecting IFC files${RESET}"
echo ""
echo -e "  ${GRAY}Use${RESET} ${CYAN}./infobim [-h | --help]${RESET} ${GRAY}for more info.${RESET}"
echo ""
