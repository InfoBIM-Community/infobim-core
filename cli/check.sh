#!/bin/bash

STACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT_DIR="$(cd "${STACK_DIR}/.." && pwd)"
CONFIG_FILE="${ROOT_DIR}/config/infobim.yaml"

source "${STACK_DIR}/message_box.sh"

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
echo -e "${CYAN}Running System Checks...${RESET}"
echo -e "${GRAY}${FULL_HLINE}${RESET}"
echo ""

ERRORS=()
WARNINGS=()

run_checks() {
    local DIR="$1"
    local NAME="$2"
    
    echo -e "${YELLOW}❯ ${WHITE}Checking ${CYAN}${NAME}${RESET}"
    
    if [ ! -d "$DIR" ]; then
         echo -e "  ${GRAY}• Directory not found: ${DIR}${RESET}"
         return
    fi

    for check_script in "$DIR"/*.sh; do
        if [ -f "$check_script" ]; then
            DESCRIPTION=""
            unset -f check
            unset -f repair
            unset -f hotfix
            
            # shellcheck disable=SC1090
            source "$check_script"
            
            if check; then
                 echo -e "  ${GREEN}✓ ${DESCRIPTION}${RESET}"
            else
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
                     if [ "$REPAIR_MODE" = true ]; then
                         echo -e "  ${YELLOW}⚡ Attempting repair for: ${DESCRIPTION}...${RESET}"
                         if type repair &>/dev/null; then
                             repair
                             
                             if check; then
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
        fi
    done
}

if [[ "$SCOPE" == "all" || "$SCOPE" == "infra" ]]; then
    run_checks "./stack/check/infra" "Infra"
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
    print_message_box "$GREEN" "Success" "System Operational" "$MSG"
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
    
    print_message_box "$RED" "Error" "System Check Failed" "$MSG"
fi

echo ""
