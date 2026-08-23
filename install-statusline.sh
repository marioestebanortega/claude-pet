#!/bin/bash
# OPCIONAL: instala el hook de statusLine para que Claude Pet reciba datos aún más frescos.
# No consume cuota. Hace copia de seguridad de settings.json antes de tocarlo.
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)/statusline-pet.py"

python3 - "$SRC" <<'PY'
import json, os, shutil, sys, time
src = sys.argv[1]
dst = os.path.expanduser("~/.claude/statusline-pet.py")
shutil.copyfile(src, dst); os.chmod(dst, 0o755)

s = os.path.expanduser("~/.claude/settings.json")
cfg = {}
if os.path.exists(s):
    shutil.copyfile(s, s + f".bak.{int(time.time())}")
    cfg = json.load(open(s))

old = cfg.get("statusLine")
if old and old.get("command", "").endswith("statusline-pet.py") is False:
    print(f"⚠️  Ya tenías un statusLine configurado:\n    {old.get('command')}\n    Se guardó copia del settings.json antes de reemplazarlo.")

cfg["statusLine"] = {
    "type": "command",
    "command": f"python3 {dst}",
    # Sin esto, la línea de estado solo se re-ejecuta tras cada mensaje del
    # asistente: si dejas Claude Code quieto, el dato de cuota se congela.
    # Con refreshInterval también corre en temporizador. Mínimo permitido: 1.
    "refreshInterval": 10,
    "padding": 1,
}
json.dump(cfg, open(s, "w"), indent=2)
print("✅ statusLine instalado. Reinicia Claude Code para verlo.")
PY
