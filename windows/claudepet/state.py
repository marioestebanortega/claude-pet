r"""
Los ajustes que sobreviven al cierre, en `%APPDATA%\ClaudePet\state.json`.

`%APPDATA%` (Roaming) y no `%LOCALAPPDATA%` a propósito: son cuatro ajustes de
usuario de unos pocos bytes, que es justo lo que Roaming está pensado para
llevarse de una máquina a otra en un dominio. Es el equivalente más cercano al
`~/Library/Preferences` de macOS y al `~/.config` de Linux.

Vive aparte de `pet.py` —de donde salió— porque el hub también los necesita y
`pet.py` carga la capa de dibujo al importarse.

Sin dependencias, como `usage.py` y `runner.py`.
"""
from __future__ import annotations

import json
import os

STATE = os.path.join(
    os.environ.get("APPDATA") or os.path.expanduser(r"~\AppData\Roaming"),
    "ClaudePet", "state.json")


def load_state() -> dict:
    try:
        with open(STATE, encoding="utf-8") as f:
            got = json.load(f)
        return got if isinstance(got, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(state: dict) -> None:
    try:
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        tmp = STATE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f)
        # Escritura atómica. En Windows `os.replace` puede lanzar PermissionError
        # si otro proceso tiene el archivo abierto; es un OSError, así que cae en
        # el `except` de abajo y el ajuste se vuelve a guardar la próxima vez.
        os.replace(tmp, STATE)
    except OSError:
        pass


def update_state(**values) -> None:
    """Lee-modifica-escribe: cada ajuste toca solo su clave, sin pisar las de
    los demás (la mascota guarda su posición desde otro sitio)."""
    state = load_state()
    state.update(values)
    save_state(state)
