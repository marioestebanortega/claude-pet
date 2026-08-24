#!/bin/bash
# Quita el hook de statusLine y su archivo de datos.
set -euo pipefail
python3 - <<'PY'
import json, os, shutil, time
s = os.path.expanduser("~/.claude/settings.json")
prev = os.path.expanduser("~/.claude/claudepet-prev-statusline.json")
if os.path.exists(s):
    try:
        cfg = json.load(open(s))
    except ValueError:
        cfg = None
    if not isinstance(cfg, dict):
        print(f"⚠️  {s} no es un objeto JSON válido; no se toca.")
    elif isinstance(cfg.get("statusLine"), dict) \
            and cfg["statusLine"].get("command", "").endswith("statusline-pet.py"):
        # Permisos propios, no los del umask: settings.json puede llevar
        # credenciales en `env`.
        bak = s + f".bak.{int(time.time())}"
        fd = os.open(bak, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as out, open(s) as orig:
            out.write(orig.read())
        if os.path.exists(prev):
            # Restaurar el statusLine que había antes de instalar el nuestro.
            try:
                cfg["statusLine"] = json.load(open(prev))
                os.remove(prev)
                print("✅ statusLine restaurado al que tenías antes.")
            except ValueError:
                cfg.pop("statusLine")
                print("⚠️  El sidecar estaba corrupto; se quitó el statusLine sin restaurar.")
        else:
            cfg.pop("statusLine")
            print("✅ statusLine removido.")
        mode = os.stat(s).st_mode & 0o777
        tmp = s + ".tmp"
        json.dump(cfg, open(tmp, "w"), indent=2)
        # `os.replace` deja el archivo con los permisos del .tmp (0644 del umask),
        # no con los del original: si el settings.json era 0600 porque lleva un
        # `env` con credenciales, escribirlo lo dejaría legible por toda la máquina.
        os.chmod(tmp, mode)
        os.replace(tmp, s)
    else:
        print("ℹ️  No estaba instalado el statusLine de Claude Pet.")
for f in ("~/.claude/statusline-pet.py", "~/.claude/pet-usage.json"):
    p = os.path.expanduser(f)
    if os.path.exists(p): os.remove(p); print("🗑  ", p)
PY
