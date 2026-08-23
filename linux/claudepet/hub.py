"""
Una sola lectura de datos y un solo temporizador para toda la aplicación.

La bandeja y la mascota enseñan lo mismo; si cada una sondeara por su cuenta se
leerían los archivos el doble de veces y podrían enseñar cifras distintas
durante unos segundos.
"""
from __future__ import annotations

import os

from gi.repository import GLib

from . import usage

POLL_SECONDS = 5


class Hub:
    def __init__(self) -> None:
        self.data: usage.Usage | None = None
        self._stamps: tuple | None = None
        self._listeners: list = []

    def subscribe(self, callback) -> None:
        """Registra un oyente. Recibe `(data, changed)`; `changed` es falso
        cuando el dato es el mismo y solo ha envejecido."""
        self._listeners.append(callback)
        if self._stamps is not None:
            callback(self.data, True)

    def start(self) -> None:
        self.refresh(force=True)
        GLib.timeout_add_seconds(POLL_SECONDS, self._tick)

    def _tick(self) -> bool:
        self.refresh()
        return True                                # seguir llamando

    def refresh(self, force: bool = False) -> None:
        stamps = tuple(
            os.path.getmtime(p) if os.path.exists(p) else None
            for p in (usage.CLAUDE_JSON, usage.STATUSLINE_JSON)
        )
        changed = force or stamps != self._stamps or self.data is None
        if changed:
            self._stamps = stamps
            self.data = usage.best()
        for callback in list(self._listeners):
            callback(self.data, changed)
