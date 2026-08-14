#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

MODULE_NAME="ifc"
MODULE_SOURCE="stack/ifc"

MAIN_CONFIG="${ROOT_DIR}/config/infobim.yaml"

if [[ ! -f "$MAIN_CONFIG" ]]; then
    echo "modules:" > "$MAIN_CONFIG"
    echo "  - ${MODULE_NAME}:" >> "$MAIN_CONFIG"
    echo "      source: ${MODULE_SOURCE}" >> "$MAIN_CONFIG"
    exit 0
fi

if grep -qE "^[[:space:]]*-[[:space:]]*${MODULE_NAME}:" "$MAIN_CONFIG"; then
    echo "Module '${MODULE_NAME}' already registered in config/infobim.yaml"
    exit 0
fi

if grep -qE "^[[:space:]]*modules:" "$MAIN_CONFIG"; then
    TMP_FILE="${MAIN_CONFIG}.tmp"
    awk -v name="$MODULE_NAME" -v src="$MODULE_SOURCE" '
        /^[[:space:]]*modules:/ {
            print
            in_mod=1
            next
        }
        in_mod && /^[^[:space:]-]/ {
            print "  - " name ":"
            print "      source: " src
            in_mod=0
        }
        { print }
        END {
            if (in_mod) {
                print "  - " name ":"
                print "      source: " src
            }
        }
    ' "$MAIN_CONFIG" > "$TMP_FILE" && mv "$TMP_FILE" "$MAIN_CONFIG"
else
    {
        echo "modules:"
        echo "  - ${MODULE_NAME}:"
        echo "      source: ${MODULE_SOURCE}"
        echo
        cat "$MAIN_CONFIG"
    } > "${MAIN_CONFIG}.tmp" && mv "${MAIN_CONFIG}.tmp" "$MAIN_CONFIG"
fi

echo "Module '${MODULE_NAME}' installed into config/infobim.yaml"

