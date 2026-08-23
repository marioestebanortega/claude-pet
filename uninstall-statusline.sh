#!/bin/bash
# Quita el hook de statusLine y su archivo de datos.
set -euo pipefail
python3 - <<'PY'
import json, os, shutil, time
s = os.path.expanduser("~/.claude/settings.json")
if os.path.exists(s):
    cfg = json.load(open(s))
    if cfg.get("statusLine", {}).get("command", "").endswith("statusline-pet.py"):
        shutil.copyfile(s, s + f".bak.{int(time.time())}")
        cfg.pop("statusLine")
        json.dump(cfg, open(s, "w"), indent=2)
        print("✅ statusLine removido.")
    else:
        print("ℹ️  No estaba instalado el statusLine de Claude Pet.")
for f in ("~/.claude/statusline-pet.py", "~/.claude/pet-usage.json"):
    p = os.path.expanduser(f)
    if os.path.exists(p): os.remove(p); print("🗑  ", p)
PY
