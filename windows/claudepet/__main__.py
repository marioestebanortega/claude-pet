"""
Punto de entrada.

`--dump`, `--icon` y `--ico` no importan nada de la interfaz a propósito: así se
puede comprobar que la lectura de datos funciona aunque falte o falle todo lo
demás, que es justo lo primero que hay que descartar en una máquina nueva.
"""
from __future__ import annotations

import sys

HOOK = "statusline-pet.py"


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
            with open(path, encoding="utf-8") as f:
                line = json.load(f).get("statusLine")
            cmd = line.get("command") if isinstance(line, dict) else None
        except Exception:
            continue
        if not isinstance(cmd, str):
            continue
        return None if _is_mine(cmd) else (f".claude/{name}", cmd)
    return None


def _is_mine(command) -> bool:
    """¿Es este el hook de Claude Pet?

    En Linux basta con `command.endswith("statusline-pet.py")`. Aquí no: el
    comando de Windows lleva delante la ruta completa del intérprete y va
    entrecomillado, así que termina en comilla. Comparar en minúsculas porque las
    rutas de Windows no distinguen mayúsculas.
    """
    return HOOK.lower() in str(command or "").lower()


def _python_console() -> str:
    """El intérprete **con consola**, para el hook y para lo que imprima.

    La app corre bajo `pythonw.exe`, que no tiene stdout: `sys.stdout` es None y
    `print` se convierte en un no-op silencioso. Si el hook se instalara con
    `pythonw`, la línea de estado saldría vacía para siempre y sin decir por qué.
    """
    import os
    exe = sys.executable or "python.exe"
    if os.path.basename(exe).lower() == "pythonw.exe":
        console = os.path.join(os.path.dirname(exe), "python.exe")
        if os.path.exists(console):
            return console
    return exe


def _dump_auto(data) -> None:
    """Estado de la consulta automática de `/usage`, que es lo que mantiene la
    cifra viva con Claude Code cerrado. Se lee del estado en disco y no del hub,
    para no arrastrar aquí nada de la interfaz."""
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
    # `usage.py` es copia literal de la de Linux —para poder compararlas de un
    # vistazo—, así que sus rutas vienen de `expanduser` con barras de Unix. Se
    # normalizan aquí, que es el único sitio donde se enseñan.
    import os
    print(f"  Archivos : solo {os.path.normpath(usage.CLAUDE_JSON)} "
          f"y {os.path.normpath(usage.STATUSLINE_JSON)}")
    print("  Red      : ninguna")
    print("  Claude Code activo ahora:", "sí" if usage.claude_code_active() else "no")
    return 0


def _icon(args: list[str]) -> int:
    from . import sprite, usage
    path = args[0] if args and not args[0].startswith("--") else "clawd.png"
    data = usage.best()
    color = sprite.BRAND
    if "--tint" in args and data:
        color = usage.MOOD_COLORS[usage.mood_for(data.worst)][0]
    with open(path, "wb") as f:
        f.write(sprite.render(color=color, night="--night" in args, cell=8))
    print("escrito", path)
    return 0


def _ico(args: list[str]) -> int:
    """El `.ico` para el acceso directo del menú Inicio. Windows no acepta un
    PNG ahí: quiere un `.ico`, un `.exe` o una `.dll`."""
    from . import sprite
    path = args[0] if args and not args[0].startswith("--") else "claudepet.ico"
    with open(path, "wb") as f:
        f.write(sprite.ico(night="--night" in args))
    print("escrito", path)
    return 0


def _hook_source() -> str | None:
    """El hook vive fuera del paquete Python: al lado de él cuando está
    instalado, y en la raíz del repo cuando se ejecuta desde el fuente."""
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    for rel in ("..", os.path.join("..", "..")):
        path = os.path.normpath(os.path.join(here, rel, HOOK))
        if os.path.exists(path):
            return path
    return None


def _replace_preserving_acl(src: str, dst: str) -> None:
    """Sustituye `dst` por `src` conservando los permisos de `dst`.

    `os.replace` es atómico también en Windows, pero el archivo resultante se
    queda con el descriptor de seguridad del `.tmp`, no con el del original.
    Cuando la ACL es puramente heredada da igual —el `.tmp` nace en la misma
    carpeta y hereda lo mismo—, pero si alguien había endurecido a mano su
    `settings.json` (quitando el ACE de Administradores, cifrándolo con EFS…),
    reescribirlo lo aflojaría sin avisar. Y ese archivo puede llevar un bloque
    `env` con credenciales.

    `ReplaceFileW` es el equivalente exacto del `os.chmod(tmp, mode)` que hace la
    versión de Linux antes de su `os.replace`: conserva ACL, atributos y fecha de
    creación del destino.
    """
    import os
    if not os.path.exists(dst):
        os.replace(src, dst)              # ReplaceFile exige que el destino exista
        return
    from . import win32 as w
    if not w.ReplaceFileW(dst, src, None, 0, None, None):
        os.replace(src, dst)              # p. ej. en volúmenes distintos


def _install_statusline(args: list[str]) -> int:
    """Pone (o quita) el hook de statusLine, que es la fuente de datos fresca.

    `~/.claude.json` se refresca muy de tarde en tarde; el hook escribe cada
    pocos segundos y además funde las cifras de todas las sesiones abiertas.
    No importa nada de la interfaz a propósito, igual que `--dump`.
    """
    import glob
    import json
    import os
    import shutil
    import time

    # `normpath` porque `expanduser("~/.claude")` deja una barra de Unix en medio
    # ("C:\\Users\\mario/.claude") y esa ruta acaba escrita en settings.json, a la
    # vista. Funciona igual, pero canta.
    claude = os.path.normpath(os.path.expanduser("~/.claude"))
    dst = os.path.join(claude, HOOK)
    settings = os.path.join(claude, "settings.json")
    prev = os.path.join(claude, "claudepet-prev-statusline.json")

    cfg = {}
    if os.path.exists(settings):
        try:
            with open(settings, encoding="utf-8") as f:
                cfg = json.load(f)
        except ValueError:
            print(f"⚠️  {settings} no es JSON válido. No lo toco.", file=sys.stderr)
            return 1
        if not isinstance(cfg, dict):
            print(f"⚠️  {settings} no contiene un objeto. No lo toco.", file=sys.stderr)
            return 1

    def backup() -> None:
        """La copia se hace DENTRO de `~\\.claude`, nunca en %TEMP%.

        En Linux esta función abre el respaldo con 0600 explícito porque el
        `settings.json` puede llevar un bloque `env` con credenciales. En Windows
        no hay un modo que poner: lo que protege el archivo es la ACL heredada
        del perfil, que ya deja fuera a los demás usuarios estándar. Por eso lo
        importante aquí es no sacar la copia de esa carpeta, que es de donde
        hereda. Se conserva solo la última, porque acumularlas multiplica las
        copias de ese mismo secreto.
        """
        if not os.path.exists(settings):
            return
        bak = f"{settings}.bak.{int(time.time())}"
        shutil.copyfile(settings, bak)
        for old_bak in glob.glob(f"{settings}.bak.*"):
            if old_bak != bak:
                try:
                    os.remove(old_bak)
                except OSError:
                    pass

    def write() -> None:
        tmp = settings + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        _replace_preserving_acl(tmp, settings)

    old = cfg.get("statusLine") or {}
    mine = _is_mine(old.get("command"))

    if "off" in args:
        if mine:
            backup()
            if os.path.exists(prev):
                # Restaurar el statusLine que había antes de instalar el nuestro.
                try:
                    with open(prev, encoding="utf-8") as f:
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
        print(f"No encuentro {HOOK}. Debería estar al lado del paquete, o en la "
              "raíz del repo si lo ejecutas desde el fuente.", file=sys.stderr)
        return 1

    if old and not mine:
        # Había un statusLine ajeno: se guarda aparte para poder restaurarlo con
        # `--install-statusline off`. No se pisa un sidecar previo.
        if not os.path.exists(prev):
            with open(prev, "w", encoding="utf-8") as f:
                json.dump(old, f, indent=2)
        print(f"⚠️  Ya tenías un statusLine propio:\n    {old.get('command')}\n"
              f"    Se guardó en {prev} y se restaura con --install-statusline off.")

    os.makedirs(claude, exist_ok=True)
    shutil.copyfile(src, dst)
    # Sin `os.chmod(0o755)`: en Windows no hay bit de ejecución, y da igual
    # porque el comando nombra al intérprete de forma explícita.
    backup()
    cfg["statusLine"] = {
        "type": "command",
        # Ruta completa del intérprete y no `python`: en Windows el `python` del
        # PATH puede ser el alias de la Microsoft Store, que mide cero bytes y
        # lo único que hace es abrir la tienda. Y `python.exe`, no `pythonw.exe`
        # (ver `_python_console`).
        #
        # `-X utf8` no es opcional: el hook imprime emojis y sin esto Python
        # codifica su salida con la página de códigos local (cp1252 en España),
        # que no sabe escribir 🐱 — el hook reventaría en cada pasada y el
        # traceback saldría en la barra de estado de Claude Code.
        "command": f'"{_python_console()}" -X utf8 "{dst}"',
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
    con docs/mascota-flotante.png. Es la prueba del rasterizador."""
    from . import draw, usage
    path = next((a for a in args if not a.startswith("--")), "pet.png")
    scale = int(next((a.split("=")[1] for a in args if a.startswith("--scale=")),
                     draw.REF_SCALE))
    draw.write_png(path, usage.best(), "--night" in args, stale=False, scale=scale)
    print("escrito", path)
    return 0


def _autostart(args: list[str]) -> int:
    """Equivalente a `SMAppService` en macOS y a la entrada `.desktop` de
    autostart en Linux: un acceso directo en la carpeta de Inicio.

    A propósito **no** se usa la clave `Run` del registro. Así toda la
    instalación se quita borrando archivos, el acceso directo se ve y se borra
    desde el propio Explorador (`shell:startup`), y no se escribe una clave de
    persistencia de las que los antivirus y los EDR miran con lupa.

    El `.lnk` no se genera aquí: hacerlo desde Python sin dependencias obligaría
    a montar el COM de `IShellLink` con ctypes, o a lanzar un PowerShell desde
    una app gráfica. El instalador ya dejó uno hecho al lado de la app y esto se
    limita a copiarlo.
    """
    import os
    import shutil

    startup = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows",
                           "Start Menu", "Programs", "Startup", "Claude Pet.lnk")
    if "off" in args:
        try:
            os.remove(startup)
            print("✅ Ya no arranca al iniciar sesión.")
        except FileNotFoundError:
            print("ℹ️  No estaba activado.")
        return 0

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template = os.path.join(here, "claudepet-autostart.lnk")
    if not os.path.exists(template):
        print("No encuentro la plantilla del acceso directo. Esto solo funciona\n"
              "con Claude Pet instalado (install-windows.ps1), no desde el fuente.",
              file=sys.stderr)
        return 1
    os.makedirs(os.path.dirname(startup), exist_ok=True)
    shutil.copyfile(template, startup)
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
    if "--ico" in args:
        return _ico([a for a in args if a != "--ico"])
    if "--pet-png" in args:
        return _pet_png([a for a in args if a != "--pet-png"])
    if "--install-statusline" in args:
        return _install_statusline([a for a in args if a != "--install-statusline"])
    if "--help" in args or "-h" in args:
        print(__doc__)
        print("  --dump              muestra el consumo y sale (no toca la interfaz)")
        print("  --icon [ruta]       escribe el PNG de Clawd  [--night] [--tint]")
        print("  --ico [ruta]        escribe el .ico del acceso directo  [--night]")
        print("  --autostart [off]   arrancar al iniciar sesión")
        print("  --install-statusline [off]  pone el hook que da el dato fresco")
        print("  --pet               solo la mascota flotante, sin bandeja")
        print("  --no-pet            solo la bandeja, sin mascota")
        print("  --pet-png [ruta]    vuelca la mascota a PNG  [--night] [--scale=N]")
        print("  sin argumentos      bandeja + mascota, según el estado guardado")
        return 0

    try:
        from .app import run
    except Exception as exc:                        # algo de Win32 no está
        print(f"No pude arrancar la aplicación: {exc}", file=sys.stderr)
        print("\nPrueba primero que la lectura funciona:", file=sys.stderr)
        print("  claudepet --dump", file=sys.stderr)
        return 1
    return run(show_tray="--pet" not in args,
               show_pet=False if "--no-pet" in args else (True if "--pet" in args else None))


if __name__ == "__main__":
    raise SystemExit(main())
