DESCRIPTION="Infra: Python Requirements"

find_infobim_pyproject() {
    local CUR="$(pwd)"
    for i in {1..12}; do
        if [ -f "$CUR/.__ontobdc__/config.yaml" ]; then
            if [ -f "$CUR/wip/pyproject.toml" ]; then
                echo "$CUR/wip/pyproject.toml"
                return 0
            fi
        fi
        local NEXT="$(dirname "$CUR")"
        if [ "$NEXT" = "$CUR" ]; then
            break
        fi
        CUR="$NEXT"
    done

    if [ -f "$(pwd)/pyproject.toml" ]; then
        echo "$(pwd)/pyproject.toml"
        return 0
    fi

    echo ""
    return 1
}

python_bin() {
    if [ -n "$VIRTUAL_ENV" ] && [ -x "$VIRTUAL_ENV/bin/python3" ]; then
        echo "$VIRTUAL_ENV/bin/python3"
        return 0
    fi
    local CUR="$(pwd)"
    for i in {1..12}; do
        if [ -x "$CUR/.venv/bin/python3" ]; then
            echo "$CUR/.venv/bin/python3"
            return 0
        fi
        local NEXT="$(dirname "$CUR")"
        if [ "$NEXT" = "$CUR" ]; then
            break
        fi
        CUR="$NEXT"
    done
    echo "python3"
    return 0
}

check() {
    PYPROJECT_FILE="$(find_infobim_pyproject)"
    if [ -z "$PYPROJECT_FILE" ]; then
        return 0
    fi

    PYTHON_BIN="$(python_bin)"

    "$PYTHON_BIN" - "$PYPROJECT_FILE" <<'PY' >/dev/null 2>&1
import sys, re
try:
    import tomllib as toml
except Exception:  # pragma: no cover
    try:
        import tomli as toml
    except Exception:
        toml = None
from importlib.metadata import distribution, PackageNotFoundError

pyproject_path = sys.argv[1]

try:
    if toml is None:
        raise RuntimeError("no toml parser")
    with open(pyproject_path, "rb") as f:
        data = toml.load(f) or {}
except Exception:
    sys.exit(1)

deps = (data.get("project") or {}).get("dependencies") or []
if not isinstance(deps, list):
    sys.exit(1)

missing = []
for d in deps:
    if not isinstance(d, str):
        continue
    pkg = re.split(r"[<>=!~;\[]", d)[0].strip()
    if not pkg:
        continue
    try:
        distribution(pkg)
    except PackageNotFoundError:
        missing.append(pkg)

sys.exit(1 if missing else 0)
PY
}

hotfix() {
    PYPROJECT_FILE="$(find_infobim_pyproject)"
    if [ -z "$PYPROJECT_FILE" ]; then
        return 0
    fi

    PYTHON_BIN="$(python_bin)"

    DEPS=$("$PYTHON_BIN" - "$PYPROJECT_FILE" <<'PY'
import sys
import re
try:
    import tomllib as toml
except Exception:  # pragma: no cover
    try:
        import tomli as toml
    except Exception:
        toml = None
from importlib.metadata import distribution, PackageNotFoundError

pyproject_path = sys.argv[1]
if toml is None:
    raise SystemExit(1)
with open(pyproject_path, "rb") as f:
    data = toml.load(f) or {}
deps = (data.get("project") or {}).get("dependencies") or []
missing = []
for d in deps:
    if not isinstance(d, str):
        continue
    spec = d.strip()
    if not spec:
        continue
    pkg = re.split(r"[<>=!~;\[]", spec)[0].strip()
    if not pkg:
        continue
    try:
        distribution(pkg)
    except PackageNotFoundError:
        missing.append(spec)
print(" ".join(missing))
PY
)

    if [ -n "$DEPS" ]; then
        "$PYTHON_BIN" -m pip install $DEPS >/dev/null 2>&1
        return $?
    fi

    return 0
}

repair() {
    hotfix
}
