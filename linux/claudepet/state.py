"""
Los ajustes que sobreviven al cierre, en `~/.config/claudepet/state.json`.

Vive aparte de `pet.py` —de donde salió— porque el hub también los necesita y
`pet.py` importa Cairo al cargarse: con `--no-pet`, en una máquina sin
`python3-gi-cairo`, importarlo desde el hub tumbaría la bandeja entera.

Sin dependencias, como `usage.py` y `runner.py`.
"""
from __future__ import annotations

import json
import os

STATE = os.path.expanduser("~/.config/claudepet/state.json")


def load_state() -> dict:
    try:
        with open(STATE) as f:
            got = json.load(f)
        return got if isinstance(got, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(state: dict) -> None:
    try:
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        tmp = STATE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(state, f)
        os.replace(tmp, STATE)                 # escritura atómica
    except OSError:
        pass


def update_state(**values) -> None:
    """Lee-modifica-escribe: cada ajuste toca solo su clave, sin pisar las de
    los demás (la mascota guarda su posición desde otro sitio)."""
    state = load_state()
    state.update(values)
    save_state(state)
