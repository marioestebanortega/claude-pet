"""
Una sola lectura de datos y un solo temporizador para toda la aplicación.

La bandeja y la mascota enseñan lo mismo; si cada una sondeara por su cuenta se
leerían los archivos el doble de veces y podrían enseñar cifras distintas
durante unos segundos.
"""
from __future__ import annotations

import os
import threading
import time

from . import runner, usage
from .state import load_state, update_state

POLL_SECONDS = 5

# Cada consulta automática arranca el CLI de Claude Code entero. `/usage` en sí
# no gasta tokens (medido con `--output-format json`: num_turns 0,
# total_cost_usd 0); lo que cuesta es el arranque.
#
# Medido aquí con `medir-cpu.ps1` en Windows 11 ARM64, tres corridas: 3,8-4,9 s
# de reloj, 1,43 s de CPU de media y un pico de ~408 MB. Sale más caro que en
# Linux (0,98 s) porque crear un proceso en Windows lo es. De esta cifra sale el
# «~X % de un núcleo» que enseña el menú.
AUTO_FORCE_CPU_SECONDS = 1.43
# Un minuto de mínimo a propósito: a 30 s serían dos picos de 400 MB por minuto
# para un dato que casi no se mueve.
AUTO_FORCE_OPTIONS = (60, 120, 300)
AUTO_FORCE_DEFAULT = 300
AUTO_FORCE_PAUSE = 300           # tras tres fallos seguidos, dejar de insistir
AUTO_FORCE_MAX_FAILURES = 3

# Avisos al cruzar 50/70/90 %, portados de `maybeNotify` de la app de macOS.
NOTIFY_TITLES = ("", "Vas por la mitad", "Ojo con el consumo", "¡Cuota casi agotada!")
NOTIFY_STEPS = (50, 70, 90)
MOOD_FACES = {"chill": "😺", "ok": "😼", "alert": "🙀", "panic": "😿", "broken": "🫥"}


class Hub:
    def __init__(self, sched) -> None:
        """`sched` es el temporizador del bucle de mensajes (`loop.Scheduler`).

        Se inyecta en vez de importarlo aquí para que este módulo no sepa nada
        de Win32 y se pueda probar suelto, y para que el archivo siga leyéndose
        como una traducción del de Linux: `sched.every` donde allí había
        `GLib.timeout_add_seconds`, y `sched.post` donde había `GLib.idle_add`.
        """
        self.sched = sched
        self.data: usage.Usage | None = None
        self._stamps: tuple | None = None
        self._listeners: list = []
        self._forcing = False

        state = load_state()
        # Encendido por defecto en todos los planes, igual que en macOS: sin
        # esto, quien cierre Claude Code se queda mirando una cifra congelada y
        # el interruptor no lo encuentra nadie. Lo que evita la sorpresa es el
        # aviso de la primera vez, no venir apagado — y `auto_force_is_due` no
        # deja que dispare mientras el hook mantenga el dato fresco.
        self.auto_force_enabled = bool(state.get("auto_force_enabled", True))
        secs = state.get("auto_force_seconds")
        self.auto_force_seconds = (int(secs) if isinstance(secs, (int, float))
                                   else AUTO_FORCE_DEFAULT)
        self.on_auto_notice = None       # aviso de la primera consulta sola
        self.on_notify = None            # avisos al cruzar 50/70/90 %
        self.notify_enabled = bool(state.get("notify_enabled", True))
        # En memoria y no en disco, igual que `lastNotifiedStep` en macOS: al
        # arrancar no se sabe si el umbral se cruzó hace un minuto o hace tres
        # días, y la guarda de `_maybe_notify` ya se encarga del arranque en frío.
        self._last_notified_step = -1
        self._poll_id = 0
        self._auto_id = 0
        self._last_auto_force = 0.0
        self._auto_failures = 0
        self._auto_paused_until = 0.0

    def subscribe(self, callback) -> None:
        """Registra un oyente. Recibe `(data, changed)`; `changed` es falso
        cuando el dato es el mismo y solo ha envejecido."""
        self._listeners.append(callback)
        if self._stamps is not None:
            callback(self.data, True)

    def start(self) -> None:
        self.refresh(force=True)
        self._poll_id = self.sched.every(POLL_SECONDS, self._tick)
        self._schedule_auto_force()

    def _tick(self) -> bool:
        self.refresh()
        return True                                # seguir llamando

    # ── Consulta automática ──────────────────────────────────
    @property
    def auto_force_is_due(self) -> bool:
        """Cuándo vale la pena gastar un arranque del CLI.

        En Team/Enterprise, cada vez que toque el temporizador: no hay otra
        fuente. En Pro/Max solo si el dato local ya está viejo —con Claude Code
        abierto el hook lo mantiene fresco y pedir `/usage` sería tirar ~1 s de
        CPU para nada—. Sin dato ninguno, preguntar siempre vale la pena.
        """
        data = self.data
        # Team/Enterprise (y "aún no hay nada"): no hay ninguna otra fuente.
        if data is None or not data.has_free_source:
            return True
        # En Pro/Max, como mucho una consulta por ventana de frescura. Sin este
        # tope, `figures_look_frozen()` se realimentaría: `/usage` reescribe
        # `~/.claude.json`, no `pet-usage.json`, así que `changed_at_ms` no se
        # mueve y la condición seguiría siendo cierta en el siguiente tic.
        if time.time() - self._last_auto_force < usage.STALE_AFTER:
            return False
        return data.is_stale or usage.figures_look_frozen()

    def set_auto_force(self, enabled: bool) -> None:
        self.auto_force_enabled = bool(enabled)
        update_state(auto_force_enabled=self.auto_force_enabled)
        self._schedule_auto_force()

    def set_auto_force_seconds(self, seconds: int) -> None:
        self.auto_force_seconds = max(60, int(seconds))
        update_state(auto_force_seconds=self.auto_force_seconds)
        self._schedule_auto_force()

    def _schedule_auto_force(self) -> None:
        if self._auto_id:
            self.sched.cancel(self._auto_id)
            self._auto_id = 0
        if not self.auto_force_enabled:
            return
        self._auto_id = self.sched.every(
            max(60, self.auto_force_seconds), self._auto_tick)

    def _auto_tick(self) -> bool:
        """Pide `/usage` sola, pero solo cuando de verdad hace falta: en Pro/Max,
        mientras Claude Code esté abierto alimentando `pet-usage.json`, el
        temporizador salta sin arrancar nada."""
        if not self.auto_force_enabled:
            self._auto_id = 0
            return False
        if time.time() < self._auto_paused_until or not self.auto_force_is_due:
            return True
        self._notice_once()
        self._last_auto_force = time.time()
        self.force_usage(self._on_auto_state)
        return True

    def _notice_once(self) -> None:
        """La primera vez que consulta sola, avisar: aunque `/usage` sea casi
        gratis, es una acción automática y no debe sorprender."""
        if load_state().get("auto_force_notified") or not self.on_auto_notice:
            return
        update_state(auto_force_notified=True)
        free = self.data is not None and self.data.has_free_source
        self.on_auto_notice(
            "Clawd consulta tu uso solo",
            "Tu dato local lleva rato parado (Claude Code cerrado), así que "
            "Clawd lo pide con «/usage». No gasta tokens; el interruptor está "
            "en el menú de la bandeja."
            if free else
            "Tu plan no publica la cuota gratis, así que Clawd la pide con "
            "«/usage» cada tanto. No gasta tokens; el intervalo y el "
            "interruptor están en el menú de la bandeja.")

    def _on_auto_state(self, running: bool, error: str | None) -> None:
        """Silencioso a propósito: la consulta sola no toca la etiqueta del
        botón "Forzar", que es feedback de lo que pidió el usuario. Lo único que
        vigila es que no se quede reintentando contra un CLI que no responde."""
        if running:
            return
        if error is None:
            self._auto_failures = 0
            return
        self._auto_failures += 1
        if self._auto_failures >= AUTO_FORCE_MAX_FAILURES:
            self._auto_failures = 0
            self._auto_paused_until = time.time() + AUTO_FORCE_PAUSE

    # ── Avisos al cruzar un umbral ───────────────────────────
    def set_notify(self, enabled: bool) -> None:
        self.notify_enabled = bool(enabled)
        update_state(notify_enabled=self.notify_enabled)

    def _maybe_notify(self) -> None:
        """Avisa solo al CRUZAR un umbral hacia arriba (50/70/90 %).

        Portado tal cual de `maybeNotify` de la app de macOS, guarda incluida:
        `step > previous` es lo que hace que solo avise al subir —bajar de banda
        al reiniciarse la ventana no es una noticia—, y la segunda mitad
        (`previous >= 0 or step >= 2`) es para el arranque en frío: abrir la app
        con un 55 % ya gastado no merece un aviso, con un 95 % sí.
        """
        data = self.data
        if data is None or not self.notify_enabled or self.on_notify is None:
            return
        worst = data.worst
        step = sum(1 for umbral in NOTIFY_STEPS if worst >= umbral)
        previous = self._last_notified_step
        self._last_notified_step = step
        if not (step > 0 and step > previous and (previous >= 0 or step >= 2)):
            return
        detail = " · ".join(f"{limit.label[:6]} {limit.percent}%"
                            for limit in data.limits if limit.percent > 0)
        face = MOOD_FACES.get(usage.mood_for(worst), "")
        self.on_notify(f"{face} {NOTIFY_TITLES[step]}", detail or f"{worst}% usado",
                       step >= len(NOTIFY_STEPS))

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

            self.sched.post(done)

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
            self._maybe_notify()
        for callback in list(self._listeners):
            callback(self.data, changed)
