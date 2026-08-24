"""
Una sola lectura de datos y un solo temporizador para toda la aplicación.

La bandeja y la mascota enseñan lo mismo; si cada una sondeara por su cuenta se
leerían los archivos el doble de veces y podrían enseñar cifras distintas
durante unos segundos.
"""
from __future__ import annotations

import os
import threading

from gi.repository import GLib

from . import runner, usage

POLL_SECONDS = 5


class Hub:
    def __init__(self) -> None:
        self.data: usage.Usage | None = None
        self._stamps: tuple | None = None
        self._listeners: list = []
        self._forcing = False

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

    def force_usage(self, on_state=None) -> None:
        """Lanza `claude -p "/usage"` en segundo plano (para no congelar la
        bandeja) y, al terminar, relee los datos. `on_state(running, error)` se
        invoca SIEMPRE en el bucle principal: primero (True, None) al arrancar y
        luego (False, error|None) al acabar."""
        if self._forcing:
            return
        self._forcing = True
        if on_state:
            on_state(True, None)

        def work() -> None:
            err = runner.force_usage()

            def done() -> bool:
                self._forcing = False
                self.refresh(force=True)           # relee el caché ya reescrito
                if on_state:
                    on_state(False, err)
                return False                        # idle_add: correr una vez

            GLib.idle_add(done)

        threading.Thread(target=work, daemon=True).start()

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
