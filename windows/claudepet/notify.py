"""
Los avisos de escritorio, y la garantía de que ninguno se pierde en silencio.

El camino normal es `Shell_NotifyIcon` con `NIF_INFO` sobre el icono que la app
ya tiene puesto: Windows 10 y 11 convierten ese globo en una notificación de
verdad, con su entrada en el centro de actividades. No hace falta registrar un
AppUserModelID, ni COM, ni WinRT, ni lanzar un PowerShell — que además es
justo el patrón que miran con lupa los antivirus.

El problema es que si el usuario tiene los avisos apagados para la app, o el
Asistente de concentración puesto, el globo se descarta y `Shell_NotifyIconW`
**devuelve TRUE igual**. Eso rompería la regla que la versión de Linux se toma
en serio (`app.py:52-65`): el aviso de que Clawd va a consultar solo es lo que
evita que una acción automática sorprenda, así que no puede perderse.

La forma de enterarse es que el shell manda `NIN_BALLOONSHOW` cuando el globo
aparece de verdad. Se arma un plazo corto; si no llega, se enseña un
`MessageBoxW`. Es el equivalente exacto del diálogo de GTK que enseña Linux
cuando falta `notify-send`.
"""
from __future__ import annotations

import threading

from . import win32 as w

DEADLINE_MS = 2500          # margen de sobra: el globo aparece al instante

_tray = None                # lo enchufa `tray.Tray` al construirse
_sched = None
_waiting: dict[int, tuple[str, str]] = {}
_next_id = 0
_dialog_open = False


def bind(tray, sched) -> None:
    """`tray.py` y `app.py` se conocen por aquí y no al revés: así `hub.py` puede
    llamar a `notify()` sin importar nada de la bandeja."""
    global _tray, _sched
    _tray, _sched = tray, sched


def notify(title: str, body: str, warning: bool = False) -> None:
    """Da el aviso. Nunca falla en silencio: o sale el globo, o sale un diálogo."""
    global _next_id
    if _tray is None or _sched is None or not _tray.balloon(title, body, warning):
        _fallback(title, body)
        return
    _next_id += 1
    ident = _next_id
    _waiting[ident] = (title, body)
    _sched.after(DEADLINE_MS, lambda: _expired(ident))


def balloon_shown() -> None:
    """La llama `tray.py` al recibir `NIN_BALLOONSHOW`: el globo se vio, así que
    ya no hace falta el respaldo. Se limpian todos los pendientes porque solo
    puede haber un globo a la vez."""
    _waiting.clear()


def _expired(ident: int) -> bool:
    pending = _waiting.pop(ident, None)
    if pending is not None:
        _fallback(*pending)
    return False                                   # `after`: una sola vez


def _fallback(title: str, body: str) -> None:
    """`MessageBoxW` en un hilo: tiene su propio bucle de mensajes, así que en el
    hilo principal bloquearía la app entera mientras el usuario no lo cierre.

    Con un cerrojo simple para que una ráfaga de avisos no apile diálogos.
    """
    global _dialog_open
    if _dialog_open:
        return
    _dialog_open = True

    def work() -> None:
        global _dialog_open
        try:
            w.MessageBoxW(None, body, f"Claude Pet — {title}",
                          w.MB_OK | w.MB_ICONINFORMATION
                          | w.MB_SETFOREGROUND | w.MB_TOPMOST)
        finally:
            _dialog_open = False

    threading.Thread(target=work, daemon=True).start()
