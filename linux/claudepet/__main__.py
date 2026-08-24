"""
Punto de entrada.

`--dump` y `--icon` no importan GTK a propósito: así se puede comprobar que la
lectura de datos funciona aunque falten las dependencias del escritorio, que es
justo lo primero que falla en otra máquina.
"""
from __future__ import annotations

import sys


def _statusline_override() -> tuple[str, str] | None:
    """El `statusLine` que manda no es siempre el del usuario: las settings del
    proyecto (`.claude/settings.json`, y la `.local` por encima) ganan sobre
    `~/.claude/settings.json`, que es donde escribe `--install-statusline`. Si en
    el directorio actual hay uno ajeno, el hook no corre aquí por mucho que el
    instalador dijera «✅ instalado». Devuelve (capa, comando)."""
    import json
    import os

    # De más a menos prioridad. Manda la PRIMERA capa que defina un statusLine,
    # sea de quien sea: si esa es la nuestra no hay conflicto, y las de debajo
    # dan igual porque ya no se leen.
    for name in ("settings.local.json", "settings.json"):
        path = os.path.join(os.getcwd(), ".claude", name)
        try:
            with open(path) as f:
                line = json.load(f).get("statusLine")
            cmd = line.get("command") if isinstance(line, dict) else None
        except Exception:
            continue
        if not isinstance(cmd, str):
            continue
        return None if cmd.endswith(HOOK) else (f".claude/{name}", cmd)
    return None


def _dump_auto(data) -> None:
    """Estado de la consulta automática de `/usage`, que es lo que mantiene la
    cifra viva con Claude Code cerrado. Se lee del estado en disco y no del hub,
    para no importar GTK aquí."""
    from . import usage
    from .state import load_state
    st = load_state()
    on = st.get("auto_force_enabled", True)
    print("\nConsulta automática de /usage (no gasta tokens):",
          "encendida" if on else "apagada")
    if not on:
        return
    if data is None or not data.has_free_source:
        secs = st.get("auto_force_seconds", 300)
        print(f"  Tu plan no publica rate_limits, así que pregunta cada {int(secs) // 60} min.")
        return
    frozen = usage.figures_look_frozen()
    print(f"  Solo si el dato pasa de {usage.STALE_AFTER // 60} min: "
          f"ahora hace {int(data.age)} s"
          + (" y las cifras llevan rato clavadas → tocaría preguntar" if frozen else ""))


def _dump() -> int:
    from . import usage
    print("claude.json  :", "OK" if usage.from_claude_json() else "no disponible")
    print("statusLine   :", "OK" if usage.from_statusline() else "no configurado")
    over = _statusline_override()
    if over:
        capa, cmd = over
        print(f"  ⚠️  {capa} de este directorio define su propio statusLine:")
        print(f"        {cmd}")
        print("      Las settings del proyecto ganan sobre ~/.claude/settings.json, así que")
        print("      aquí el hook de Claude Pet NO se ejecuta, esté instalado o no.")
        print("      Quítalo de ahí, o haz que ese comando llame también a statusline-pet.py.")

    data = usage.best()
    if data is None:
        print("SIN DATOS →", usage.empty_reason())
        _dump_auto(None)
        return 1

    from datetime import datetime
    print(f"fuente elegida: {data.source} | hace {int(data.age)} s")
    for limit in data.limits:
        reset = ""
        if limit.resets_at:
            reset = "se reinicia " + datetime.fromtimestamp(limit.resets_at).strftime("%a %d %H:%M")
        print(f"  {limit.label:<26} {limit.percent:>3}%  {limit.detail or '':<22} {reset}")
    print(f"peor = {data.worst} → humor {usage.mood_for(data.worst)}")

    _dump_auto(data)

    print("\nPermisos que usa esta app:")
    print(f"  Archivos : solo {usage.CLAUDE_JSON} y {usage.STATUSLINE_JSON}")
    print("  Red      : ninguna")
    print("  Claude Code activo ahora:", "sí" if usage.claude_code_active() else "no")
    return 0


def _icon(args: list[str]) -> int:
    from . import sprite, usage
    path = args[0] if args else "clawd.png"
    data = usage.best()
    color = sprite.BRAND
    if "--tint" in args and data:
        color = usage.MOOD_COLORS[usage.mood_for(data.worst)][0]
    with open(path, "wb") as f:
        f.write(sprite.render(color=color, night="--night" in args, cell=8))
    print("escrito", path)
    return 0


HOOK = "statusline-pet.py"


def _hook_source() -> str | None:
    """El hook vive fuera del paquete Python: en /usr/lib/claudepet cuando se
    instala por .deb, y en la raíz del repo cuando se ejecuta desde el fuente."""
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    for rel in ("..", os.path.join("..", "..")):
        path = os.path.normpath(os.path.join(here, rel, HOOK))
        if os.path.exists(path):
            return path
    return None


def _install_statusline(args: list[str]) -> int:
    """Pone (o quita) el hook de statusLine, que es la fuente de datos fresca.

    `~/.claude.json` se refresca muy de tarde en tarde; el hook escribe cada
    pocos segundos y además funde las cifras de todas las sesiones abiertas.
    No importa GTK a propósito, igual que `--dump`: tiene que funcionar en una
    máquina sin escritorio.
    """
    import glob
    import json
    import os
    import shutil
    import time

    claude = os.path.expanduser("~/.claude")
    dst = os.path.join(claude, HOOK)
    settings = os.path.join(claude, "settings.json")
    prev = os.path.join(claude, "claudepet-prev-statusline.json")

    cfg = {}
    if os.path.exists(settings):
        try:
            with open(settings) as f:
                cfg = json.load(f)
        except ValueError:
            print(f"⚠️  {settings} no es JSON válido. No lo toco.", file=sys.stderr)
            return 1
        if not isinstance(cfg, dict):
            print(f"⚠️  {settings} no contiene un objeto. No lo toco.", file=sys.stderr)
            return 1

    def backup() -> None:
        """Copia con permisos propios, no los del umask: `settings.json` puede
        llevar un bloque `env` con credenciales. Se conserva solo la última,
        porque acumularlas multiplica las copias de ese mismo secreto."""
        if not os.path.exists(settings):
            return
        bak = f"{settings}.bak.{int(time.time())}"
        fd = os.open(bak, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as out, open(settings) as orig:
            out.write(orig.read())
        for old_bak in glob.glob(f"{settings}.bak.*"):
            if old_bak != bak:
                try:
                    os.remove(old_bak)
                except OSError:
                    pass

    def write() -> None:
        # Escritura atómica: nunca dejar el settings.json a medio escribir.
        mode = os.stat(settings).st_mode & 0o777 if os.path.exists(settings) else 0o600
        tmp = settings + ".tmp"
        with open(tmp, "w") as f:
            json.dump(cfg, f, indent=2)
        # `os.replace` deja el archivo con los permisos del .tmp (0644 del umask),
        # no con los del original: si el settings.json era 0600 porque lleva un
        # `env` con credenciales, escribirlo lo dejaría legible por toda la máquina.
        os.chmod(tmp, mode)
        os.replace(tmp, settings)

    old = cfg.get("statusLine") or {}
    mine = str(old.get("command", "")).endswith(HOOK)

    if "off" in args:
        if mine:
            backup()
            if os.path.exists(prev):
                # Restaurar el statusLine que había antes de instalar el nuestro.
                try:
                    with open(prev) as f:
                        cfg["statusLine"] = json.load(f)
                    os.remove(prev)
                    print("✅ statusLine restaurado al que tenías antes.")
                except ValueError:
                    cfg.pop("statusLine")
                    print("⚠️  El sidecar estaba corrupto; se quitó sin restaurar.")
            else:
                cfg.pop("statusLine")
                print("✅ statusLine quitado.")
            write()
        elif old:
            print("ℹ️  El statusLine configurado no es el de Claude Pet; lo dejo.")
        else:
            print("ℹ️  No estaba puesto.")
        for path in (dst, os.path.join(claude, "pet-usage.json")):
            if os.path.exists(path):
                os.remove(path)
                print("🗑 ", path)
        return 0

    src = _hook_source()
    if src is None:
        print(f"No encuentro {HOOK}. Si instalaste por .deb debería estar en "
              "/usr/lib/claudepet/.", file=sys.stderr)
        return 1

    if old and not mine:
        # Había un statusLine ajeno: se guarda aparte para poder restaurarlo con
        # `--install-statusline off`. No se pisa un sidecar previo.
        if not os.path.exists(prev):
            with open(prev, "w") as f:
                json.dump(old, f, indent=2)
        print(f"⚠️  Ya tenías un statusLine propio:\n    {old.get('command')}\n"
              f"    Se guardó en {prev} y se restaura con --install-statusline off.")

    os.makedirs(claude, exist_ok=True)
    shutil.copyfile(src, dst)
    os.chmod(dst, 0o755)
    backup()
    cfg["statusLine"] = {
        "type": "command",
        "command": f"python3 {dst}",
        # Sin esto la línea de estado solo se re-ejecuta tras cada mensaje del
        # asistente: si dejas Claude Code quieto, el dato de cuota se congela.
        "refreshInterval": 10,
        "padding": 1,
    }
    write()
    print("✅ statusLine instalado. Reinicia Claude Code para verlo.")
    return 0


def _pet_png(args: list[str]) -> int:
    """Vuelca la mascota a PNG sin necesitar pantalla, para poder compararla
    con docs/mascota-flotante.png."""
    from . import pet, usage
    path = next((a for a in args if not a.startswith("--")), "pet.png")
    pet.write_png(path, usage.best(), "--night" in args,
                  stale=False, scale=int(next(
                      (a.split("=")[1] for a in args if a.startswith("--scale=")),
                      pet.REF_SCALE)))
    print("escrito", path)
    return 0


def _autostart(args: list[str]) -> int:
    """Equivalente a SMAppService en macOS: una entrada .desktop en autostart."""
    import os
    path = os.path.expanduser("~/.config/autostart/claudepet.desktop")
    if "off" in args:
        try:
            os.remove(path)
            print("✅ Ya no arranca al iniciar sesión.")
        except FileNotFoundError:
            print("ℹ️  No estaba activado.")
        return 0

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=Claude Pet\n"
            "Comment=Vigila tu consumo de Claude Code\n"
            "Exec=claudepet\n"
            "Icon=claudepet\n"
            "Terminal=false\n"
            "X-GNOME-Autostart-enabled=true\n"
        )
    print("✅ Arrancará al iniciar sesión.")
    print("   Para quitarlo: claudepet --autostart off")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if "--dump" in args:
        return _dump()
    if "--autostart" in args:
        return _autostart(args)
    if "--icon" in args:
        return _icon([a for a in args if a != "--icon"])
    if "--pet-png" in args:
        return _pet_png([a for a in args if a != "--pet-png"])
    if "--install-statusline" in args:
        return _install_statusline([a for a in args if a != "--install-statusline"])
    if "--help" in args or "-h" in args:
        print(__doc__)
        print("  --dump              muestra el consumo y sale (no necesita GTK)")
        print("  --icon [ruta]       escribe el PNG de Clawd  [--night] [--tint]")
        print("  --autostart [off]   arrancar al iniciar sesión")
        print("  --install-statusline [off]  pone el hook que da el dato fresco")
        print("  --pet               solo la mascota flotante, sin bandeja")
        print("  --no-pet            solo la bandeja, sin mascota")
        print("  --pet-png [ruta]    vuelca la mascota a PNG  [--night] [--scale=N]")
        print("  sin argumentos      bandeja + mascota, según el estado guardado")
        return 0

    try:
        from .app import run
    except Exception as exc:                        # GTK ausente o roto
        print(f"No pude arrancar el applet: {exc}", file=sys.stderr)
        print("\nPrueba primero que la lectura funciona:", file=sys.stderr)
        print("  claudepet --dump", file=sys.stderr)
        return 1
    return run(show_tray="--pet" not in args,
               show_pet=False if "--no-pet" in args else (True if "--pet" in args else None))


if __name__ == "__main__":
    raise SystemExit(main())
