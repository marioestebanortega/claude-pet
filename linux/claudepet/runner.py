"""
"Forzar": pide a Claude Code que consulte el servidor con `claude -p "/usage"`,
lo que reescribe el caché local (~/.claude.json) con cifras frescas. Es el
equivalente del botón "Forzar" de la app de macOS.

Pese al nombre, `/usage` no gasta tokens: el CLI lo resuelve sin un turno del
modelo (medido con `--output-format json`: `num_turns` 0, `total_cost_usd` 0).
Lo que sí cuesta es arrancar el CLI —~1,3 s de CPU y un pico de 580 MB—, así que
solo se lanza cuando el usuario lo pide a mano.

Sin dependencias de GTK a propósito (como `usage.py`): así se puede probar suelto.
"""
from __future__ import annotations

import os
import subprocess


def force_usage(timeout: float = 120) -> str | None:
    """Ejecuta `claude -p "/usage"`. Devuelve None si fue bien, o un mensaje de
    error corto si falló. BLOQUEA hasta que termina: llámalo desde un hilo, nunca
    desde el bucle de GTK."""
    env = dict(os.environ)
    # Un applet lanzado desde el .desktop puede traer un PATH mínimo; nos
    # aseguramos de encontrar `claude` donde suele instalarse (npm global,
    # ~/.local/bin, /usr/local/bin…). Igual que hace la app de macOS.
    extra = [os.path.expanduser("~/.local/bin"), "/usr/local/bin", "/usr/bin", "/bin"]
    env["PATH"] = os.pathsep.join(extra + [env.get("PATH", "")])
    try:
        r = subprocess.run(
            ["claude", "-p", "/usage"],
            cwd=os.path.expanduser("~"),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
    except FileNotFoundError:
        return "No encuentro el binario `claude` en el PATH."
    except subprocess.TimeoutExpired:
        return f"El CLI tardó demasiado (>{int(timeout)} s) y se canceló."
    except OSError as e:
        return f"No pude lanzar el CLI: {e}"
    if r.returncode != 0:
        out = (r.stdout or b"").decode("utf-8", "replace").strip()
        return out[:200] if out else f"El CLI salió con código {r.returncode}"
    return None
