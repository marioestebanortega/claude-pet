"""
El bucle de mensajes, los temporizadores y el paso de trabajo desde otros hilos.

Es el único módulo que sabe qué bucle mueve la aplicación, para que cambiarlo
sea tocar un archivo. Hoy es un `GetMessageW` pelado, y **no** tkinter, por una
razón concreta: `WM_TIMER` lo despacha cualquier bucle modal, incluido el de
`TrackPopupMenu`, que está abierto todo el rato que el usuario tarde en leer el
menú de la bandeja. La cola de Tcl no se atiende durante esos bucles, así que
con `root.after()` la mascota dejaría de respirar y el sondeo de datos se
pararía mientras el menú está abierto.

`Scheduler` imita a propósito la interfaz de GLib que usa `hub.py` en Linux
(`every` ↔ `timeout_add_seconds`, `post` ↔ `idle_add`, `cancel` ↔
`source_remove`, con el mismo contrato de devolver True para seguir), para que
los dos `hub.py` se puedan comparar de un vistazo.
"""
from __future__ import annotations

import sys
import threading
import traceback

from . import win32 as w

# Mensajes propios. WM_APP es el rango reservado para la aplicación.
WM_APP_INVOKE = w.WM_APP + 1           # ejecutar algo llegado de otro hilo
WM_APP_TRAY = w.WM_APP + 2             # el icono de la bandeja habla por aquí

# Mensajes registrados en todo el sistema: se piden por nombre, y así el mismo
# nombre da el mismo número en cualquier proceso.
WM_TASKBAR_CREATED = w.RegisterWindowMessageW("TaskbarCreated")
WM_CLAUDEPET_SHOW = w.RegisterWindowMessageW("ClaudePet.Show")

# Los trampolines de ctypes tienen que sobrevivir a la función que los crea: si
# la única referencia es una variable local, el recolector libera el puente y el
# siguiente mensaje mata al intérprete sin dejar traza ninguna.
_procs: list = []
_classes: dict[str, object] = {}
# El WNDPROC se registra por CLASE, no por ventana, así que no puede quedarse
# capturando una ventana concreta: si dos ventanas compartieran clase, los
# mensajes de la segunda acabarían en el manejador de la primera. El reparto se
# hace aquí, por `hwnd`.
_windows: dict[int, "Window"] = {}

_quit_code = 0


def _wndproc(hwnd, msg, wparam, lparam):
    """Todo el cuerpo va envuelto: una excepción que se escape de un callback de
    ctypes devuelve basura como LRESULT y deja al shell con una idea equivocada
    de la ventana. Mejor imprimirla y seguir por el camino de siempre.

    Los mensajes que llegan *durante* `CreateWindowExW` (WM_NCCREATE, WM_CREATE)
    no encuentran todavía la ventana en el registro; caen a `DefWindowProcW`,
    que es exactamente lo que hay que hacer con ellos.
    """
    try:
        win = _windows.get(hwnd)
        if win is not None and win.on_message is not None:
            got = win.on_message(msg, wparam, lparam)
            if got is not None:
                return got
    except Exception:                              # noqa: BLE001 — a propósito
        traceback.print_exc(file=sys.stderr)
    return w.DefWindowProcW(hwnd, msg, wparam, lparam)


class Window:
    """Una ventana con su `WNDPROC` en Python.

    La ventana que lleva el icono de la bandeja **no puede ser de solo mensajes**
    (`HWND_MESSAGE`): esas no reciben difusiones, y `TaskbarCreated` —el aviso de
    que el Explorador se ha reiniciado y hay que volver a poner el icono— es
    justo una difusión. Se usa una ventana normal que sencillamente no se enseña
    nunca. Además, así puede tomar el primer plano, que es lo que necesita
    `TrackPopupMenu` para cerrarse bien.
    """

    def __init__(self, cls_name: str, title: str = "Claude Pet",
                 ex_style: int = w.WS_EX_TOOLWINDOW, style: int = w.WS_POPUP,
                 rect: tuple[int, int, int, int] = (0, 0, 0, 0),
                 on_message=None) -> None:
        self.on_message = on_message
        self.hwnd = 0
        hinst = w.GetModuleHandleW(None)

        if cls_name not in _classes:
            proc = w.WNDPROC(_wndproc)
            _procs.append(proc)                   # ver el comentario de _procs
            cls = w.WNDCLASSEXW()
            cls.cbSize = w.ctypes.sizeof(w.WNDCLASSEXW)
            cls.style = w.CS_DBLCLKS
            cls.lpfnWndProc = proc
            cls.hInstance = hinst
            cls.hCursor = w.LoadCursorW(None, w.LPCWSTR(w.IDC_ARROW))
            cls.lpszClassName = cls_name
            if not w.RegisterClassExW(w.ctypes.byref(cls)):
                err = w.ctypes.get_last_error()
                if err != w.ERROR_CLASS_ALREADY_EXISTS:
                    raise OSError(f"RegisterClassExW falló ({err})")
            _classes[cls_name] = cls              # que no se recoja antes de tiempo

        x, y, width, height = rect
        self.hwnd = w.CreateWindowExW(ex_style, cls_name, title, style,
                                      x, y, width, height,
                                      None, None, hinst, None)
        if not self.hwnd:
            raise OSError(f"CreateWindowExW falló ({w.ctypes.get_last_error()})")
        _windows[self.hwnd] = self

    def destroy(self) -> None:
        if self.hwnd:
            _windows.pop(self.hwnd, None)
            w.DestroyWindow(self.hwnd)
            self.hwnd = 0


class Scheduler:
    """Temporizadores y trabajo diferido, todos colgando de una sola ventana."""

    def __init__(self, hwnd: int) -> None:
        self.hwnd = hwnd
        self._timers: dict[int, tuple] = {}       # id → (función, repetir)
        self._next_timer = 1000
        self._posted: dict[int, object] = {}
        self._next_post = 1
        self._lock = threading.Lock()             # `post` llega desde otros hilos

    # ── Temporizadores ───────────────────────────────────────
    def every(self, seconds: float, fn) -> int:
        """Como `GLib.timeout_add_seconds`: `fn()` devuelve True para seguir."""
        return self._start(int(max(1, round(seconds * 1000))), fn, repeat=True)

    def after(self, millis: int, fn) -> int:
        """Una sola vez, pasados `millis` milisegundos."""
        return self._start(int(max(1, millis)), fn, repeat=False)

    def _start(self, millis: int, fn, repeat: bool) -> int:
        self._next_timer += 1
        tid = self._next_timer
        self._timers[tid] = (fn, repeat)
        if not w.SetTimer(self.hwnd, tid, millis, None):
            del self._timers[tid]
            raise OSError(f"SetTimer falló ({w.ctypes.get_last_error()})")
        return tid

    def cancel(self, tid: int) -> None:
        if self._timers.pop(tid, None) is not None:
            w.KillTimer(self.hwnd, tid)

    def _fire(self, tid: int) -> None:
        entry = self._timers.get(tid)
        if entry is None:
            w.KillTimer(self.hwnd, tid)           # de una cancelación a destiempo
            return
        fn, repeat = entry
        keep = False
        try:
            keep = bool(fn())
        finally:
            if not (repeat and keep):
                self.cancel(tid)

    # ── Desde otros hilos ────────────────────────────────────
    def post(self, fn) -> None:
        """Como `GLib.idle_add`: ejecuta `fn()` en el hilo del bucle.

        El invocable se guarda en un diccionario bajo un número que va subiendo,
        y por el mensaje solo viaja ese número. Mandar `id(objeto)` sería un
        fallo de conteo de referencias esperando a la siguiente pasada del
        recolector.
        """
        with self._lock:
            self._next_post += 1
            ident = self._next_post
            self._posted[ident] = fn
        if not w.PostMessageW(self.hwnd, WM_APP_INVOKE, ident, 0):
            with self._lock:                      # la cola está llena o no hay ventana
                self._posted.pop(ident, None)

    def _invoke(self, ident: int) -> None:
        with self._lock:
            fn = self._posted.pop(ident, None)
        if fn is not None:
            fn()

    # ── Enganche con la ventana ──────────────────────────────
    def handle(self, msg: int, wparam: int, lparam: int) -> int | None:
        """Devuelve 0 si el mensaje era suyo, o None para dejarlo pasar."""
        if msg == w.WM_TIMER:
            self._fire(int(wparam))
            return 0
        if msg == WM_APP_INVOKE:
            self._invoke(int(wparam))
            return 0
        return None


def run() -> int:
    """El bucle. Devuelve el código de salida que se pasó a `quit()`."""
    msg = w.wintypes.MSG()
    ref = w.ctypes.byref(msg)
    while True:
        got = w.GetMessageW(ref, None, 0, 0)
        if got == 0:                               # WM_QUIT
            break
        if got == -1:                              # error de verdad
            raise OSError(f"GetMessageW falló ({w.ctypes.get_last_error()})")
        w.TranslateMessage(ref)
        w.DispatchMessageW(ref)
    return _quit_code


def quit(code: int = 0) -> None:
    global _quit_code
    _quit_code = code
    w.PostQuitMessage(code)
