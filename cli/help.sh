#!/bin/bash

BOLD='\033[1m'
RESET='\033[0m'
CYAN='\033[36m'
GRAY='\033[90m'
WHITE='\033[37m'

TERM_WIDTH=$(tput cols)
SEPARATOR=$(printf '─%.0s' $(seq 1 "$TERM_WIDTH"))

echo ""
echo -e "  ${BOLD}InfoBIM CLI${RESET} ${GRAY}v0.1.0${RESET}"
echo -e "  ${GRAY}BIM on the inside, drawings on the outside, data for everyone.${RESET}"
echo ""
echo -e "${GRAY}${SEPARATOR}${RESET}"
echo ""
echo -e "  ${WHITE}USAGE${RESET}"
echo -e "    ${GRAY}./infobim [command]${RESET}"
echo ""
echo -e "  ${WHITE}GENERAL COMMANDS${RESET}"
echo ""
echo -e "    ${CYAN}install [--docker] [--colab] [--lang <code>]${RESET}"
echo -e "      ${GRAY}Installs the stack and prepares the environment.${RESET}"
echo -e "      ${GRAY}Default: Sets up Python virtual environment (venv).${RESET}"
echo -e "      ${GRAY}--docker: Also sets up Docker environment.${RESET}"
echo -e "      ${GRAY}--colab: Optimizes for Google Colab (skips venv, creates env file).${RESET}"
echo -e "      ${GRAY}--lang: Sets the CLI language in config/infobim.yaml.${RESET}"
echo ""
echo -e "    ${CYAN}check [--repair]${RESET}"
echo -e "      ${GRAY}Verifies the system and project state.${RESET}"
echo -e "      ${GRAY}Use --repair to attempt automatic fixes.${RESET}"
echo ""

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONFIG_FILE="${ROOT_DIR}/config/infobim.yaml"

if [[ -f "$CONFIG_FILE" ]]; then
  while IFS='|' read -r MOD_NAME MOD_SRC; do
    [[ -z "$MOD_NAME" || -z "$MOD_SRC" ]] && continue
    MODULE_DIR="${ROOT_DIR}/${MOD_SRC}"
    MODULE_HELP="${MODULE_DIR}/help.sh"
    if [[ -f "$MODULE_HELP" ]]; then
      # shellcheck disable=SC1090
      source "$MODULE_HELP"
      if type "infobim_help_${MOD_NAME}" >/dev/null 2>&1; then
        "infobim_help_${MOD_NAME}"
      elif type infobim_help >/dev/null 2>&1; then
        infobim_help
      fi
    fi
  done < <(
    awk '
      /^[[:space:]]*-[[:space:]]*[A-Za-z0-9_-]+:/ {
        line=$0
        gsub(/^[[:space:]]*-[[:space:]]*/,"",line)
        sub(/:.*/,"",line)
        mod=line
      }
      /^[[:space:]]*source:[[:space:]]*/ {
        src=$0
        sub(/^[[:space:]]*source:[[:space:]]*/,"",src)
        gsub(/[[:space:]]+$/,"",src)
        if (mod != "") {
          print mod "|" src
        }
      }
    ' "$CONFIG_FILE"
  )
fi

echo -e "${GRAY}${SEPARATOR}${RESET}"
echo ""
