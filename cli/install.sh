#!/bin/bash

BOLD='\033[1m'
RESET='\033[0m'
CYAN='\033[36m'
GRAY='\033[90m'
WHITE='\033[37m'
GREEN='\033[32m'
YELLOW='\033[33m'
RED='\033[31m'

echo ""
echo -e "  ${CYAN}Starting InfoBIM stack installation...${RESET}"

if [[ "$1" == "module" ]]; then
    shift
    MODULE_PATH="$1"

    if [[ -z "$MODULE_PATH" ]]; then
        echo -e "  ${RED}Error:${RESET} missing module path."
        echo -e "  ${GRAY}Usage:${RESET} ./infobim install module <path>"
        exit 1
    fi

    if [[ ! -d "$MODULE_PATH" ]]; then
        echo -e "  ${RED}Error:${RESET} module path not found: ${MODULE_PATH}"
        exit 1
    fi

    MODULE_ABS_PATH="$(cd "$MODULE_PATH" && pwd)"
    MODULE_INSTALL_SCRIPT="${MODULE_ABS_PATH}/install.sh"

    if [[ ! -f "$MODULE_INSTALL_SCRIPT" ]]; then
        echo -e "  ${RED}Error:${RESET} install.sh not found in module path: ${MODULE_PATH}"
        exit 1
    fi

    echo -e "  ${CYAN}Installing module from${RESET} ${MODULE_PATH}"
    (
        cd "$MODULE_ABS_PATH" || exit 1
        bash "./install.sh"
    )
    exit $?
fi

IS_COLAB=false
USE_DOCKER=false
LANG_VALUE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --colab)
            IS_COLAB=true
            ;;
        --docker)
            USE_DOCKER=true
            ;;
        --lang)
            shift
            if [[ -n "$1" ]]; then
                LANG_VALUE="$1"
            fi
            ;;
        --lang=*)
            LANG_VALUE="${1#--lang=}"
            ;;
        *)
            ;;
    esac
    shift
done

if [[ ! -d "./stack" || ! -f "./stack/init.sh" ]]; then
    echo -e "${CYAN}Checking git repository...${RESET}"
    if ! git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
        echo -e "${YELLOW}Not a git repository. Initializing...${RESET}"
        git init
    else
        echo -e "${GREEN}Git repository detected.${RESET}"
    fi

    echo -e "${CYAN}Installing stack submodule...${RESET}"
    git submodule add -f https://github.com/InfoBIM-Community/infobim-ifc.git stack
    if [ $? -ne 0 ]; then
        echo ""
        echo -e "${RED}Installation failed:${RESET} Failed to install stack!"
        exit 1
    fi
else
    echo -e "${GREEN}Stack submodule already installed.${RESET}"
fi

if [[ -f "./stack/infobim.sh" ]]; then
    if [[ ! -L "./infobim" ]]; then
        echo -e "${CYAN}Linking infobim...${RESET}"
        ln -sf ./stack/infobim.sh ./infobim
    fi
fi

if [[ -d "./stack/ontobdc" ]]; then
    if [[ -e "./ontobdc" && ! -L "./ontobdc" ]]; then
        echo -e "${CYAN}Removing existing ontobdc...${RESET}"
        rm -rf ./ontobdc
    fi

    if [[ ! -L "./ontobdc" ]]; then
        echo -e "${CYAN}Linking ontobdc...${RESET}"
        ln -sf ./stack/ontobdc ./ontobdc
    fi
fi

if [ "$IS_COLAB" = false ]; then
    echo ""
    echo -e "${CYAN}Setting up Python Environment (venv)...${RESET}"
    bash ./stack/cli/check.sh --repair --scope infra
else
    echo ""
    echo -e "${YELLOW}Skipping venv setup (Colab mode).${RESET}"
fi

if [[ "$USE_DOCKER" = true && "$IS_COLAB" = false ]]; then
    echo ""
    echo -e "${CYAN}Setting up Docker Environment...${RESET}"
    bash ./stack/cli/check.sh --repair --scope ifc
fi

CONFIG_FILE="./config/infobim.yaml"

if [[ -f "$CONFIG_FILE" ]]; then
    ENGINE_VALUE="venv"
    if [ "$IS_COLAB" = true ]; then
        ENGINE_VALUE="colab"
    elif [ "$USE_DOCKER" = true ]; then
        ENGINE_VALUE="docker"
    fi

    if grep -qE '^[[:space:]]*engine:' "$CONFIG_FILE"; then
        sed -i '' -E "s/^[[:space:]]*engine:.*/      engine: ${ENGINE_VALUE}/" "$CONFIG_FILE"
    else
        TMP_FILE="${CONFIG_FILE}.tmp"
        awk -v val="$ENGINE_VALUE" '
            BEGIN { inserted = 0 }
            {
                print $0
                if (!inserted && $0 ~ /- *install:/) {
                    print "      engine: " val
                    inserted = 1
                }
            }
        ' "$CONFIG_FILE" > "$TMP_FILE" && mv "$TMP_FILE" "$CONFIG_FILE"
    fi
fi

if [[ -n "$LANG_VALUE" ]]; then
    if [[ -f "$CONFIG_FILE" ]]; then
        if grep -qE '^[[:space:]]*language:' "$CONFIG_FILE"; then
            sed -i '' -E "s/^[[:space:]]*language:.*/language: ${LANG_VALUE}/" "$CONFIG_FILE"
        else
            echo "language: ${LANG_VALUE}" >> "$CONFIG_FILE"
        fi
    fi
fi

echo ""
echo -e "${CYAN}Verifying System Health...${RESET}"
bash ./infobim check --repair

echo ""
echo -e "${GREEN}Installation finished. Environment is ready.${RESET}"
echo ""
