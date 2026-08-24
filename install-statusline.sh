#!/bin/bash
# OPCIONAL: instala el hook de statusLine para que Claude Pet reciba datos aún más frescos.
# No consume cuota. Hace copia de seguridad de settings.json antes de tocarlo.
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)/statusline-pet.py"

python3 - "$SRC" <<'PY'
import glob, json, os, shutil, sys, time
src = sys.argv[1]
dst = os.path.expanduser("~/.claude/statusline-pet.py")
prev = os.path.expanduser("~/.claude/claudepet-prev-statusline.json")
shutil.copyfile(src, dst); os.chmod(dst, 0o755)

def backup(path):
    """Copia de seguridad con permisos propios, no los del umask.

    `settings.json` puede llevar un bloque `env` con credenciales, así que la
    copia nace en 0600 en vez de heredar el 0644 que da `open()`. Y se conserva
    solo la última: acumularlas multiplica las copias de ese mismo secreto.
    """
    bak = f"{path}.bak.{int(time.time())}"
    fd = os.open(bak, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as out, open(path) as orig:
        out.write(orig.read())
    for old_bak in sorted(glob.glob(f"{path}.bak.*")):
        if old_bak != bak:
            try:
                os.remove(old_bak)
            except OSError:
                pass


s = os.path.expanduser("~/.claude/settings.json")
cfg = {}
if os.path.exists(s):
    backup(s)
    try:
        cfg = json.load(open(s))
    except ValueError:
        print(f"❌ {s} no es JSON válido. Se dejó una copia (.bak.*) y no se tocó nada.")
        sys.exit(1)
    if not isinstance(cfg, dict):
        print(f"❌ {s} no es un objeto JSON. Se dejó una copia (.bak.*) y no se tocó nada.")
        sys.exit(1)

old = cfg.get("statusLine")
mine = isinstance(old, dict) and old.get("command", "").endswith("statusline-pet.py")
if isinstance(old, dict) and not mine:
    # Había un statusLine ajeno: se guarda aparte para poder restaurarlo al
    # desinstalar. No se pisa un sidecar previo (una reinstalación no debe
    # perder el original de la primera vez).
    if not os.path.exists(prev):
        json.dump(old, open(prev, "w"), indent=2)
    print(f"⚠️  Ya tenías un statusLine propio:\n    {old.get('command')}\n"
          f"    Se guardó en {prev} y se restaura con ./uninstall-statusline.sh.")

cfg["statusLine"] = {
    "type": "command",
    "command": f"python3 {dst}",
    # Sin esto, la línea de estado solo se re-ejecuta tras cada mensaje del
    # asistente: si dejas Claude Code quieto, el dato de cuota se congela.
    # Con refreshInterval también corre en temporizador. Mínimo permitido: 1.
    "refreshInterval": 10,
    "padding": 1,
}
# Escritura atómica: nunca dejar el settings.json a medio escribir.
mode = os.stat(s).st_mode & 0o777 if os.path.exists(s) else 0o600
tmp = s + ".tmp"
json.dump(cfg, open(tmp, "w"), indent=2)
# `os.replace` deja el archivo con los permisos del .tmp (0644 del umask),
# no con los del original: si el settings.json era 0600 porque lleva un
# `env` con credenciales, escribirlo lo dejaría legible por toda la máquina.
os.chmod(tmp, mode)
os.replace(tmp, s)
print("✅ statusLine instalado. Reinicia Claude Code para verlo.")
PY
