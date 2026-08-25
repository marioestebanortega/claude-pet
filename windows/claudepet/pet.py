"""
La mascota flotante: una ventana en capas sobre el escritorio.

`WS_EX_LAYERED` + `UpdateLayeredWindow` con alfa por píxel, y no una ventana
normal con color clave. El diseño lo pide: el plato va al 94 %, la pista de los
anillos al 13 % y el borde al 12 %, y con transparencia por color eso es
imposible —es de un bit, o el píxel está o no está—.

De propina salen tres cosas que con color clave habría que fabricar:

- **Los clics atraviesan lo transparente.** El propio alfa hace de zona
  sensible: no hay que calcular ninguna región.
- **`WS_EX_NOACTIVATE`**: clicar a Clawd no le roba el foco al editor. En algo
  que vive encima de todo el día, eso importa bastante.
- **`WS_EX_TOOLWINDOW`**: fuera de la barra de tareas y del Alt+Tab, que es lo
  que en GTK hacen `set_skip_taskbar_hint` y `set_skip_pager_hint`.

A diferencia de Linux, aquí no hay ninguna rama de Wayland: la ventana siempre
se puede colocar, así que la posición se guarda y se restaura sin excepciones, y
«Traer a esta pantalla» significa de verdad la pantalla donde está el cursor.

El dibujo vive en `draw.py` y no sabe nada de esta ventana, igual que en Linux:
así `--pet-png` puede volcarlo sin pantalla ninguna y compararlo con
`docs/mascota-flotante.png`.
"""
from __future__ import annotations

import ctypes
import time

from . import draw, loop, menu, usage
from . import win32 as w
from .state import load_state, update_state

CLASS_NAME = "ClaudePetWindow"
WIN_W, WIN_H = 200, 192          # mismo lienzo que la ventana de macOS
EDGE_MARGIN = 24                 # separación al borde al colocarla por defecto
BREATHE_MS = 1700
SAVE_DEBOUNCE_MS = 400

# Identificadores del menú del clic derecho. Empiezan en 1 (ver `menu.FIRST_ID`).
ID_HIDE = 1
ID_REFRESH = 2
ID_FORCE = 3
ID_RECENTER = 4
ID_AUTO = 5
ID_QUIT = 6


def _ago(seconds: float) -> str:
    seconds = int(max(0, seconds))
    if seconds < 60:
        return f"{seconds} s"
    if seconds < 3600:
        return f"{seconds // 60} min"
    if seconds < 86400:
        return f"{seconds // 3600} h"
    return f"{seconds // 86400} d"


class PetWindow:
    def __init__(self, hub, on_quit=None) -> None:
        self.hub = hub
        self.sched = hub.sched
        self.on_quit = on_quit
        self._visible = False
        self._poke_until = 0.0
        self._poke_id = 0
        self._bob = -draw.BOB
        self._save_id = 0
        self._dragging = False
        self._grab = (0, 0)
        self._hovering = False
        self._tracking = False
        self._bubble: str | None = None

        x, y = self._restore_position()
        self.window = loop.Window(
            CLASS_NAME, "Claude Pet",
            ex_style=(w.WS_EX_LAYERED | w.WS_EX_TOOLWINDOW
                      | w.WS_EX_TOPMOST | w.WS_EX_NOACTIVATE),
            style=w.WS_POPUP, rect=(x, y, WIN_W, WIN_H),
            on_message=self._on_message)
        self.hwnd = self.window.hwnd

        self._scale = 1.0
        self._canvas = self._plate = None
        self._hdc_screen = w.GetDC(None)
        self._hdc = self._hbm = self._old_bm = None
        self._bits = None
        self._build_surface()

        self.sched.every(BREATHE_MS / 1000, self._breathe)
        hub.subscribe(self._on_data)

    # ── La superficie ────────────────────────────────────────
    def _build_surface(self) -> None:
        """Crea (o rehace) el DIB del tamaño que toque para este DPI."""
        self._release_surface()
        self._scale = w.dpi_for(self.hwnd) / 96
        width = max(1, int(round(WIN_W * self._scale)))
        height = max(1, int(round(WIN_H * self._scale)))
        self._size = (width, height)
        self._canvas = draw.Canvas(width, height)
        self._plate = draw.Canvas(width, height)

        self._hdc = w.CreateCompatibleDC(self._hdc_screen)
        info = w.dib_header(width, height)
        bits = w.LPVOID()
        self._hbm = w.CreateDIBSection(self._hdc, ctypes.byref(info),
                                       w.DIB_RGB_COLORS, ctypes.byref(bits),
                                       None, 0)
        if not self._hbm or not bits:
            raise OSError("CreateDIBSection falló para la mascota")
        self._bits = bits
        self._old_bm = w.SelectObject(self._hdc, self._hbm)
        w.SetWindowPos(self.hwnd, None, 0, 0, width, height,
                       w.SWP_NOMOVE | w.SWP_NOZORDER | w.SWP_NOACTIVATE)
        self.redraw(plate=True)

    def _release_surface(self) -> None:
        if self._hdc:
            if self._old_bm is not None:
                w.SelectObject(self._hdc, self._old_bm)
            if self._hbm:
                w.DeleteObject(self._hbm)
            w.DeleteDC(self._hdc)
        self._hdc = self._hbm = self._old_bm = None
        self._bits = None

    # ── Pintura ──────────────────────────────────────────────
    @property
    def _stale(self) -> bool:
        data = self.hub.data
        return bool(data and data.is_stale and usage.claude_code_active())

    def _origin(self) -> tuple[float, float]:
        """Igual que el `translate((w - DESIGN) / 2, BUBBLE_H)` de Linux."""
        size = draw.DESIGN * self._scale
        return ((self._size[0] - size) / 2, draw.BUBBLE_H * self._scale)

    def redraw(self, plate: bool = False) -> None:
        """`plate=True` solo cuando cambia algo que no sea la animación."""
        if self._canvas is None:
            return
        size = draw.DESIGN * self._scale
        data = self.hub.data
        stale = self._stale
        if plate:
            self._plate.clear()
            draw.draw_dial(self._plate, data, size, stale, origin=self._origin())
        self._canvas.copy_from(self._plate)

        poking = self._poking
        draw.draw_mascot(self._canvas, data, draw.is_night(), size, stale,
                         origin=self._origin(),
                         bob=self._bob - (0.5 if poking else 0),
                         eyes="happy" if poking else "open",
                         mouth=4 if poking else 0)
        # El saludo manda sobre el tooltip, y no al revés: para clicar hay que
        # pasar el ratón por encima, así que un clic SIEMPRE ocurre en pleno
        # hover. Con la prioridad al revés, el saludo no se veía nunca. En Linux
        # no se plantea porque el tooltip es una ventana aparte de GTK; aquí los
        # dos comparten el mismo bocadillo.
        text = self._greeting(data) if poking else self._bubble
        if text:
            ox, oy = self._origin()
            draw.draw_bubble(self._canvas, ox + size / 2, oy - 3 * self._scale,
                             size, text)
        self._blit()

    def _blit(self) -> None:
        if not (self._hdc and self._bits):
            return
        blob = bytes(self._canvas.buf)
        ctypes.memmove(self._bits, blob, len(blob))
        width, height = self._size
        rect = w.wintypes.RECT()
        w.GetWindowRect(self.hwnd, ctypes.byref(rect))
        dst = w.wintypes.POINT(rect.left, rect.top)
        src = w.wintypes.POINT(0, 0)
        size = w.wintypes.SIZE(width, height)
        w.UpdateLayeredWindow(self.hwnd, self._hdc_screen, ctypes.byref(dst),
                              ctypes.byref(size), self._hdc, ctypes.byref(src),
                              0, ctypes.byref(w.BLEND_ALPHA), w.ULW_ALPHA)

    # ── Colocación ───────────────────────────────────────────
    def _work_area(self, monitor) -> tuple[int, int, int, int]:
        info = w.MONITORINFO()
        info.cbSize = ctypes.sizeof(w.MONITORINFO)
        if not w.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return (0, 0, 1024, 768)
        r = info.rcWork
        return (r.left, r.top, r.right - r.left, r.bottom - r.top)

    def _default_position(self) -> tuple[int, int]:
        """Abajo a la derecha del monitor **donde está el cursor**, a 24 px.

        Linux siempre va al monitor principal porque GTK no da otra cosa cómoda;
        aquí `MonitorFromPoint` hace que «Traer a esta pantalla» signifique
        literalmente lo que dice.
        """
        point = w.wintypes.POINT()
        w.GetCursorPos(ctypes.byref(point))
        monitor = w.MonitorFromPoint(point, w.MONITOR_DEFAULTTONEAREST)
        x, y, width, height = self._work_area(monitor)
        scale = getattr(self, "_scale", 1.0)
        return (x + width - int(WIN_W * scale) - EDGE_MARGIN,
                y + height - int(WIN_H * scale) - EDGE_MARGIN)

    def _on_any_monitor(self, x: int, y: int) -> bool:
        """Una sola llamada en vez del bucle sobre monitores de Linux; además
        descarta bien una posición guardada en una pantalla ya desenchufada."""
        point = w.wintypes.POINT(int(x), int(y))
        return bool(w.MonitorFromPoint(point, w.MONITOR_DEFAULTTONULL))

    def _restore_position(self) -> tuple[int, int]:
        state = load_state()
        x, y = state.get("x"), state.get("y")
        if (isinstance(x, int) and isinstance(y, int)
                and self._on_any_monitor(x, y)):
            return x, y
        return self._default_position()

    def recenter(self) -> None:
        x, y = self._default_position()
        w.SetWindowPos(self.hwnd, w.HWND_TOPMOST, x, y, 0, 0,
                       w.SWP_NOSIZE | w.SWP_NOACTIVATE)
        self._remember(x, y)
        self._blit()

    def _remember(self, x: int, y: int) -> bool:
        """Las coordenadas se guardan **en píxeles físicos de pantalla**, que es
        lo que toma `SetWindowPos` con conciencia de DPI por monitor."""
        self._save_id = 0
        update_state(x=int(x), y=int(y))
        return False

    def _remember_soon(self) -> None:
        if self._save_id:
            self.sched.cancel(self._save_id)
        rect = w.wintypes.RECT()
        w.GetWindowRect(self.hwnd, ctypes.byref(rect))
        x, y = rect.left, rect.top
        # Pequeño debounce: al arrastrar llegan muchísimos eventos.
        self._save_id = self.sched.after(SAVE_DEBOUNCE_MS,
                                         lambda: self._remember(x, y))

    # ── Visibilidad ──────────────────────────────────────────
    def get_visible(self) -> bool:
        return self._visible

    def show_pet(self) -> None:
        update_state(pet_visible=True)
        self._visible = True
        # Pintar ANTES de enseñarla: si no, aparece un fotograma con el búfer
        # sin estrenar.
        self.redraw(plate=True)
        w.ShowWindow(self.hwnd, w.SW_SHOWNOACTIVATE)
        w.SetWindowPos(self.hwnd, w.HWND_TOPMOST, 0, 0, 0, 0,
                       w.SWP_NOMOVE | w.SWP_NOSIZE | w.SWP_NOACTIVATE)

    def hide_pet(self) -> None:
        update_state(pet_visible=False)
        self._visible = False
        w.ShowWindow(self.hwnd, w.SW_HIDE)

    # ── Datos y animación ────────────────────────────────────
    def _on_data(self, data, changed: bool) -> None:
        if changed or self._stale:
            self.redraw(plate=True)

    def _tooltip(self, data) -> str:
        if data is None:
            return usage.empty_reason()
        parts = [f"Sesión {data.session_pct}%"]
        if data.weekly is not None:
            parts.append(f"Semana {data.week_pct}%")
        line = " · ".join(parts)
        age = _ago(data.age)
        if data.is_stale and usage.claude_code_active():
            return f"{line}\n⚠ dato de hace {age}, puede estar viejo"
        return f"{line}\nhace {age}"

    def _greeting(self, data) -> str:
        if data is None:
            return "aún no hay cifras"
        return f"{data.session_pct}% de sesión\n{data.week_pct}% de semana"

    def _breathe(self) -> bool:
        self._bob = draw.BOB if self._bob < 0 else -draw.BOB
        if self._visible:
            self.redraw()
        return True

    @property
    def _poking(self) -> bool:
        return time.monotonic() < self._poke_until

    def poke(self) -> None:
        """Saluda. De paso relee los archivos, que es gratis."""
        self._poke_until = time.monotonic() + draw.POKE_SECONDS
        self.hub.refresh(force=True)
        self.redraw()
        if self._poke_id:
            self.sched.cancel(self._poke_id)
        self._poke_id = self.sched.after(int(draw.POKE_SECONDS * 1000),
                                         self._end_poke)

    def _end_poke(self) -> bool:
        self._poke_id = 0
        self._poke_until = 0.0
        self.redraw()
        return False

    # ── Menú ─────────────────────────────────────────────────
    def _popup(self, x: int, y: int) -> None:
        m = menu.Menu()
        m.item(ID_HIDE, "Ocultar del escritorio")
        m.item(ID_REFRESH, "Actualizar ahora")
        m.item(ID_FORCE, "Forzar (/usage)")
        m.item(ID_RECENTER, "Traer a esta pantalla")
        # También aquí, y no solo en la bandeja: con `--pet` no hay bandeja, y
        # sin este interruptor la consulta automática no se podría apagar.
        m.item(ID_AUTO, "Consultar /usage sola (no gasta tokens)",
               checked=self.hub.auto_force_enabled)
        m.sep()
        m.item(ID_QUIT, "Salir de Claude Pet")
        try:
            chosen = m.track(self.hwnd, x, y)
        finally:
            m.destroy()
        if chosen == ID_HIDE:
            self.hide_pet()
        elif chosen == ID_REFRESH:
            self.hub.refresh(force=True)
        elif chosen == ID_FORCE:
            self.hub.force_usage()
        elif chosen == ID_RECENTER:
            self.recenter()
        elif chosen == ID_AUTO:
            self.hub.set_auto_force(not self.hub.auto_force_enabled)
        elif chosen == ID_QUIT:
            (self.on_quit or loop.quit)()

    # ── Eventos ──────────────────────────────────────────────
    def _track_mouse(self) -> None:
        """Hay que rearmarlo tras cada `WM_MOUSELEAVE`/`WM_MOUSEHOVER`."""
        if self._tracking:
            return
        tme = w.TRACKMOUSEEVENT()
        tme.cbSize = ctypes.sizeof(w.TRACKMOUSEEVENT)
        tme.dwFlags = w.TME_LEAVE | w.TME_HOVER
        tme.hwndTrack = self.hwnd
        tme.dwHoverTime = w.HOVER_DEFAULT
        if w.TrackMouseEvent(ctypes.byref(tme)):
            self._tracking = True

    def _on_message(self, msg: int, wparam: int, lparam: int):
        if msg == w.WM_MOUSEACTIVATE:
            # Que clicar a Clawd no le quite el foco a lo que el usuario estuviera
            # escribiendo. Es la contrapartida de WS_EX_NOACTIVATE.
            return w.MA_NOACTIVATE

        if msg == w.WM_LBUTTONDOWN:
            # Saludar en la pulsación y arrastrar con el movimiento, igual que
            # Linux: así no hace falta distinguir un clic de un arrastre.
            self.poke()
            rect = w.wintypes.RECT()
            w.GetWindowRect(self.hwnd, ctypes.byref(rect))
            point = w.wintypes.POINT()
            w.GetCursorPos(ctypes.byref(point))
            self._grab = (point.x - rect.left, point.y - rect.top)
            self._dragging = True
            w.SetCapture(self.hwnd)
            return 0

        if msg == w.WM_MOUSEMOVE:
            if self._dragging:
                point = w.wintypes.POINT()
                w.GetCursorPos(ctypes.byref(point))
                w.SetWindowPos(self.hwnd, None,
                               point.x - self._grab[0], point.y - self._grab[1],
                               0, 0,
                               w.SWP_NOSIZE | w.SWP_NOZORDER | w.SWP_NOACTIVATE)
                self._blit()
            else:
                self._track_mouse()
            return 0

        if msg == w.WM_LBUTTONUP:
            if self._dragging:
                self._dragging = False
                w.ReleaseCapture()
                self._remember_soon()
            return 0

        if msg == w.WM_MOUSEHOVER:
            self._tracking = False
            # El tooltip reutiliza el bocadillo que la mascota ya sabe dibujar,
            # en vez de un control de comctl32: menos código y se parece a la
            # app en vez de a un control de Windows.
            self._bubble = self._tooltip(self.hub.data)
            self.redraw()
            return 0

        if msg == w.WM_MOUSELEAVE:
            self._tracking = False
            if self._bubble is not None:
                self._bubble = None
                self.redraw()
            return 0

        if msg == w.WM_RBUTTONUP:
            point = w.wintypes.POINT()
            w.GetCursorPos(ctypes.byref(point))
            self._popup(point.x, point.y)
            return 0

        if msg == w.WM_DPICHANGED:
            # Arrastrarla de un monitor al 100 % a otro al 150 % es justo lo que
            # la deja borrosa o cortada si esto no se atiende: hay que rehacer el
            # DIB al tamaño nuevo y aceptar el rectángulo que sugiere Windows.
            suggested = ctypes.cast(lparam,
                                    ctypes.POINTER(w.wintypes.RECT)).contents
            self._build_surface()
            w.SetWindowPos(self.hwnd, None, suggested.left, suggested.top,
                           self._size[0], self._size[1],
                           w.SWP_NOZORDER | w.SWP_NOACTIVATE)
            self._blit()
            return 0

        if msg == w.WM_DESTROY:
            self.dispose()
            return 0
        return None

    def dispose(self) -> None:
        self._release_surface()
        if self._hdc_screen:
            w.ReleaseDC(None, self._hdc_screen)
            self._hdc_screen = None
