"""
Punto de entrada.

`--dump` y `--icon` no importan GTK a propósito: así se puede comprobar que la
lectura de datos funciona aunque falten las dependencias del escritorio, que es
justo lo primero que falla en otra máquina.
"""
from __future__ import annotations

import sys


def _dump() -> int:
    from . import usage
    print("claude.json  :", "OK" if usage.from_claude_json() else "no disponible")
    print("statusLine   :", "OK" if usage.from_statusline() else "no configurado")

    data = usage.best()
    if data is None:
        print("SIN DATOS →", usage.empty_reason())
        return 1

    from datetime import datetime
    print(f"fuente elegida: {data.source} | hace {int(data.age)} s")
    for limit in data.limits:
        reset = ""
        if limit.resets_at:
            reset = "se reinicia " + datetime.fromtimestamp(limit.resets_at).strftime("%a %d %H:%M")
        print(f"  {limit.label:<26} {limit.percent:>3}%  {limit.detail or '':<22} {reset}")
    print(f"peor = {data.worst} → humor {usage.mood_for(data.worst)}")

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
    import json
    import os
    import shutil
    import time

    claude = os.path.expanduser("~/.claude")
    dst = os.path.join(claude, HOOK)
    settings = os.path.join(claude, "settings.json")

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
        if os.path.exists(settings):
            shutil.copyfile(settings, f"{settings}.bak.{int(time.time())}")

    def write() -> None:
        with open(settings, "w") as f:
            json.dump(cfg, f, indent=2)

    old = cfg.get("statusLine") or {}
    mine = str(old.get("command", "")).endswith(HOOK)

    if "off" in args:
        if mine:
            backup()
            cfg.pop("statusLine")
            write()
            print("✅ statusLine quitado.")
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
        print(f"⚠️  Ya tenías un statusLine configurado:\n    {old.get('command')}\n"
              "    Se guarda copia del settings.json antes de reemplazarlo.")

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
