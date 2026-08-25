"""
"Forzar": pide a Claude Code que consulte el servidor con `claude -p "/usage"`,
lo que reescribe el caché local (~/.claude.json) con cifras frescas. Es el
equivalente del botón "Forzar" de la app de macOS.

Pese al nombre, `/usage` no gasta tokens: el CLI lo resuelve sin un turno del
modelo (medido con `--output-format json`: `num_turns` 0, `total_cost_usd` 0).
Lo que sí cuesta es arrancar el CLI entero, así que no se lanza a la ligera: o
lo pide el usuario a mano (bandeja, clic derecho de la mascota) o lo pide el hub
cuando el dato local se ha quedado congelado y no hay ninguna fuente que lo
refresque (`Hub.auto_force_is_due`).

Sin dependencias de la interfaz a propósito (como `usage.py`): así se puede
probar suelto con `python -c "from claudepet import runner; print(runner.force_usage())"`.
"""
from __future__ import annotations

import os
import shutil
import subprocess

# La app corre bajo `pythonw.exe`, que no tiene consola. `claude` sí es un
# programa de consola, así que sin esto Windows le crearía una: una ventana
# negra parpadeando en la cara del usuario cada vez que Clawd consulta sola,
# cada cinco minutos, para siempre.
CREATE_NO_WINDOW = 0x08000000
# Para poder matar el árbol entero si se pasa de tiempo (ver `force_usage`).
CREATE_NEW_PROCESS_GROUP = 0x00000200


def _extra_dirs() -> list[str]:
    """Sitios donde suele acabar `claude`, por si el PATH que hereda la app no
    los trae: un proceso arrancado desde un acceso directo no pasa por el perfil
    del shell, igual que en Linux un applet lanzado desde el .desktop. Es lo
    mismo que hacen la app de macOS y la de Linux, con las rutas de aquí."""
    home = os.path.expanduser("~")
    local = os.environ.get("LOCALAPPDATA") or os.path.join(home, "AppData", "Local")
    roaming = os.environ.get("APPDATA") or os.path.join(home, "AppData", "Roaming")
    return [
        os.path.join(home, ".local", "bin"),            # instalador nativo
        os.path.join(roaming, "npm"),                   # npm -g deja aquí claude.cmd
        os.path.join(local, "Programs", "claude"),
        os.path.join(local, "Microsoft", "WinGet", "Links"),
    ]


def find_claude() -> str | None:
    """Resuelve `claude` a una ruta absoluta.

    En Windows no basta con pasarle el nombre a `subprocess`. El instalador
    nativo deja un `claude.exe`, pero el de npm deja un `claude.cmd`, que NO es
    un ejecutable: `CreateProcess` no sabe lanzarlo y saldría un
    `FileNotFoundError` diciendo que no existe un archivo que sí está ahí.
    `shutil.which` sí lo encuentra, porque consulta `PATHEXT`, y sabiendo ya la
    extensión se puede decidir cómo lanzarlo.
    """
    path = os.pathsep.join(_extra_dirs() + [os.environ.get("PATH", "")])
    return shutil.which("claude", path=path)


def _kill_tree(pid: int) -> None:
    """`Popen.kill()` mata solo al hijo directo. Si `claude` era el `.cmd` de
    npm, el `node.exe` de debajo sobrevive con la tubería abierta y el
    `communicate()` de después se queda esperando para siempre."""
    try:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=CREATE_NO_WINDOW, timeout=15)
    except (OSError, subprocess.SubprocessError):
        pass


def force_usage(timeout: float = 120) -> str | None:
    """Ejecuta `claude -p "/usage"`. Devuelve None si fue bien, o un mensaje de
    error corto si falló. BLOQUEA hasta que termina: llámalo desde un hilo, nunca
    desde el bucle de mensajes."""
    exe = find_claude()
    if exe is None:
        return (r"No encuentro `claude`. Miré en el PATH, en ~\.local\bin "
                r"y en %APPDATA%\npm.")

    cmd = [exe, "-p", "/usage"]
    if exe.lower().endswith((".cmd", ".bat")):
        # Un .cmd es un script, no un ejecutable: lo tiene que interpretar
        # cmd.exe. `/d` salta el AutoRun del registro (que podría imprimir cosas
        # en medio de la salida) y `/s` hace que cmd no reinterprete las comillas
        # internas, que es lo que salva una ruta con espacios.
        cmd = [os.environ.get("COMSPEC") or "cmd.exe", "/d", "/s", "/c", *cmd]

    try:
        # Bajo `pythonw` el stdin heredado no es válido, y un `.cmd` que intente
        # leerlo se quedaría bloqueado: DEVNULL explícito.
        proc = subprocess.Popen(
            cmd,
            cwd=os.path.expanduser("~"),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            creationflags=CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP,
        )
    except FileNotFoundError:
        return "No encuentro el binario `claude`."
    except OSError as e:
        return f"No pude lanzar el CLI: {e}"

    try:
        out, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_tree(proc.pid)
        try:
            out, _ = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        return f"El CLI tardó demasiado (>{int(timeout)} s) y se canceló."

    if proc.returncode != 0:
        text = (out or b"").decode("utf-8", "replace").strip()
        return text[:200] if text else f"El CLI salió con código {proc.returncode}"
    return None

