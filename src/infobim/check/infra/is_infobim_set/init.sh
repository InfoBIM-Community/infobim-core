#!/bin/bash
DESCRIPTION="Infra: Infobim Capability Configured"
find_config() {
    local CUR="$(pwd)"
    for i in {1..7}; do
        if [ -f "$CUR/.__ontobdc__/config.yaml" ]; then echo "$CUR/.__ontobdc__/config.yaml"; return 0; fi
        local NEXT="$(dirname "$CUR")"
        if [ "$NEXT" = "$CUR" ]; then break; fi
        CUR="$NEXT"
    done
    echo ""
    return 1
}
check() {
    local CFG="$(find_config)"
    if [ -z "$CFG" ]; then return 1; fi
    python3 - "$CFG" <<'PY' >/dev/null
import sys, yaml
p=sys.argv[1]
try:
    with open(p,'r') as f:
        cfg=yaml.safe_load(f) or {}
except Exception:
    sys.exit(1)
cap=cfg.get('capability') or {}
pkg=cap.get('package') or []
param=cap.get('parameter') or []
need_pkg={'infobim.module'}
need_param={'infobim.run.core.strategy'}
ok = need_pkg.issubset(set(pkg)) and need_param.issubset(set(param))
sys.exit(0 if ok else 1)
PY
    return $?
}
hotfix() {
    local CFG="$(find_config)"
    if [ -z "$CFG" ]; then return 1; fi
    python3 - "$CFG" <<'PY'
import sys, yaml, os
p=sys.argv[1]
try:
    cfg={}
    if os.path.isfile(p):
        with open(p,'r') as f:
            cfg=yaml.safe_load(f) or {}
except Exception:
    cfg={}
cap=cfg.get('capability')
if not isinstance(cap, dict):
    cap={}
    cfg['capability']=cap
pkg=cap.get('package')
if not isinstance(pkg, list):
    pkg=[]
cap['package']=list(dict.fromkeys(pkg+['infobim.module']))
param=cap.get('parameter')
if not isinstance(param, list):
    param=[]
cap['parameter']=list(dict.fromkeys(param+['infobim.run.core.strategy']))
with open(p,'w') as f:
    yaml.safe_dump(cfg, f, sort_keys=False)
PY
    return 0
}
