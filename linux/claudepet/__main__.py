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
    if "--help" in args or "-h" in args:
        print(__doc__)
        print("  --dump              muestra el consumo y sale (no necesita GTK)")
        print("  --icon [ruta]       escribe el PNG de Clawd  [--night] [--tint]")
        print("  --autostart [off]   arrancar al iniciar sesión")
        print("  sin argumentos      arranca el applet de bandeja")
        return 0

    try:
        from .tray import main as tray_main
    except Exception as exc:                        # GTK ausente o roto
        print(f"No pude arrancar el applet: {exc}", file=sys.stderr)
        print("\nPrueba primero que la lectura funciona:", file=sys.stderr)
        print("  claudepet --dump", file=sys.stderr)
        return 1
    return tray_main()


if __name__ == "__main__":
    raise SystemExit(main())
