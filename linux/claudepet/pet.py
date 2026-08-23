"""
Mascota flotante: ventana sin marco sobre el escritorio.

El dibujo (`draw_pet`) no depende de la ventana a propósito: así se puede volcar
a PNG sin pantalla ninguna y compararlo con `docs/mascota-flotante.png`, que es
la referencia exacta salida del código de macOS.

Todas las medidas están en unidades de diseño con `size = 96`, igual que
`MascotView`. Para dibujar más grande se escala el contexto (`cr.scale`), no las
constantes: así la costura de 0,5 entre celdas escala con el resto, como en
SwiftUI.
"""
from __future__ import annotations

import json
import math
import os

import cairo

from . import sprite, usage

# ─────────────────────────────────────────────────────────────
# Proporciones (MascotView de macOS, verificadas contra la referencia)
# ─────────────────────────────────────────────────────────────
PLATE_PAD = 0.028
OUTER_W = 0.072
INNER_W = 0.056
INNER_INSET = 0.105
CLAWD_W = 0.48

PLATE_RGB = (0x59, 0x59, 0x5E)
PLATE_ALPHA = 0.94
PLATE_EDGE_ALPHA = 0.12
PLATE_EDGE_W = 0.5
TRACK_ALPHA = 0.13

# Lienzo del sprite: deja sitio arriba para el gorrito y a la derecha para
# accesorios. Clawd va desplazado dentro de él.
CANVAS_COLS, CANVAS_ROWS = 15, 12
CLAWD_DX, CLAWD_DY = 2, 4
CLAWD_OFF_X, CLAWD_OFF_Y = 0.5, -1.5      # en celdas, centra a Clawd en el anillo
SEAM = 0.5                                 # evita costuras finas entre celdas
BOB = 0.3                                  # flotación, en celdas

BADGE_GAP = 8.0                            # medido en la imagen de referencia
BADGE_PAD_X, BADGE_PAD_Y = 8.0, 2.5
BADGE_FONT = 11.0
BADGE_EDGE_ALPHA = 0.28
BADGE_EDGE_W = 0.5
BADGE_FAMILY = "Ubuntu"                    # fontconfig sustituye si no está

BUBBLE_H = 66.0                            # hueco para el bocadillo, encima
DESIGN = 96.0
POKE_SECONDS = 2.8

STATE = os.path.expanduser("~/.config/claudepet/state.json")


def _rgb(value: int) -> tuple[float, float, float]:
    return ((value >> 16 & 0xFF) / 255, (value >> 8 & 0xFF) / 255, (value & 0xFF) / 255)


def is_night(hour: int | None = None) -> bool:
    """Gorrito entre las 18:00 y las 6:00. (Espejo de `tray._is_night`.)"""
    if hour is None:
        import datetime
        hour = datetime.datetime.now().hour
    return hour >= 18 or hour < 6


# ─────────────────────────────────────────────────────────────
# Dibujo
# ─────────────────────────────────────────────────────────────

def _ring(cr: cairo.Context, cx: float, cy: float, radius: float,
          width: float, pct: int) -> None:
    """Pista tenue + arco de color, desde las 12 y en sentido horario."""
    cr.set_line_width(width)
    cr.set_line_cap(cairo.LINE_CAP_BUTT)
    cr.set_source_rgba(1, 1, 1, TRACK_ALPHA)
    cr.arc(cx, cy, radius, 0, 2 * math.pi)
    cr.stroke()

    if pct <= 0:
        return
    # Cada anillo se colorea por SU propio porcentaje, no por el humor global.
    cr.set_source_rgb(*_rgb(usage.MOOD_COLORS[usage.mood_for(pct)][0]))
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    start = -math.pi / 2
    cr.arc(cx, cy, radius, start, start + 2 * math.pi * min(pct, 100) / 100)
    cr.stroke()


def _clawd(cr: cairo.Context, cx: float, cy: float, size: float, night: bool,
           bob: float, eyes: str, mouth: int, color: int) -> None:
    cell = size * CLAWD_W / sprite.COLS
    ox = cx - CANVAS_COLS * cell / 2 + cell * CLAWD_OFF_X
    oy = cy - CANVAS_ROWS * cell / 2 + cell * (CLAWD_OFF_Y + bob)

    def put(col: int, row: int, tone: int) -> None:
        cr.set_source_rgb(*_rgb(tone))
        cr.rectangle(ox + col * cell, oy + row * cell, cell + SEAM, cell + SEAM)
        cr.fill()

    for r, line in enumerate(sprite.body_grid(eyes, mouth)):
        for c, on in enumerate(line):
            if on:
                put(CLAWD_DX + c, CLAWD_DY + r, color)
    for r in sprite.ARM_ROWS:                              # bracitos laterales
        put(CLAWD_DX, CLAWD_DY + r, color)
        put(CLAWD_DX + sprite.COLS - 1, CLAWD_DY + r, color)

    if night:
        for layer, tone in ((sprite.CAP_BODY, sprite.CAP_COLOR),
                            (sprite.CAP_TRIM, sprite.CAP_TRIM_COLOR)):
            for r, line in enumerate(layer):
                for c, ch in enumerate(line):
                    if ch == "#":
                        put(CLAWD_DX + c, CLAWD_DY - 3 + r, tone)


def _capsule(cr: cairo.Context, x: float, y: float, w: float, h: float) -> None:
    r = h / 2
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, math.pi / 2)
    cr.arc(x + r, y + r, r, math.pi / 2, 3 * math.pi / 2)
    cr.close_path()


def _badge(cr: cairo.Context, cx: float, top: float, size: float,
           text: str, deep: int) -> None:
    k = size / DESIGN
    cr.select_font_face(BADGE_FAMILY, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    cr.set_font_size(BADGE_FONT * k)
    ascent, descent = cr.font_extents()[0], cr.font_extents()[1]
    ext = cr.text_extents(text)

    h = ascent + descent + 2 * BADGE_PAD_Y * k
    w = ext.width + 2 * BADGE_PAD_X * k
    x = cx - w / 2

    _capsule(cr, x, top, w, h)
    cr.set_source_rgb(*_rgb(deep))
    cr.fill_preserve()
    cr.set_source_rgba(1, 1, 1, BADGE_EDGE_ALPHA)
    cr.set_line_width(BADGE_EDGE_W * k)
    cr.stroke()

    cr.set_source_rgb(1, 1, 1)
    cr.move_to(x + (w - ext.width) / 2 - ext.x_bearing, top + BADGE_PAD_Y * k + ascent)
    cr.show_text(text)


def draw_pet(cr, data, night, size=96, stale=False, *,
             bob=-BOB, eyes="open", mouth=0, tinted=False):
    """Dibuja plato + anillos + Clawd + badge en el contexto Cairo `cr`.

    El conjunto plato+anillos ocupa un cuadrado `size`×`size` con la esquina
    superior izquierda en el (0,0) del contexto. Los anillos se salen de ese
    cuadrado medio grosor, y el badge queda debajo, centrado.
    """
    cx = cy = size / 2
    mood = "broken" if (data is None or stale) else usage.mood_for(data.worst)

    # Plato
    cr.set_source_rgba(*[c / 255 for c in PLATE_RGB], PLATE_ALPHA)
    cr.arc(cx, cy, cx - size * PLATE_PAD, 0, 2 * math.pi)
    cr.fill_preserve()
    cr.set_source_rgba(1, 1, 1, PLATE_EDGE_ALPHA)
    cr.set_line_width(PLATE_EDGE_W * size / DESIGN)
    cr.stroke()

    # Anillos: exterior la semana, interior la sesión. Si el plan solo separa
    # una dimensión, un único anillo del ancho del exterior.
    session = data.session_pct if data else 0
    week = data.week_pct if data else 0
    secondary = data is not None and data.weekly is not None
    if secondary:
        _ring(cr, cx, cy, cx, size * OUTER_W, week)
        _ring(cr, cx, cy, cx - size * INNER_INSET, size * INNER_W, session)
    else:
        _ring(cr, cx, cy, cx, size * OUTER_W, session)

    _clawd(cr, cx, cy, size, night, bob, eyes, mouth,
           usage.MOOD_COLORS[mood][0] if tinted else sprite.BRAND)

    text = f"{session}/{week}%" if secondary else f"{session}%"
    if data is None:
        text = "0/0%"
    if stale:
        text = "⏱ " + text
    _badge(cr, cx, size + BADGE_GAP * size / DESIGN, size, text,
           usage.MOOD_COLORS[mood][1])


def _bubble(cr, cx: float, bottom: float, size: float, text: str) -> None:
    """Bocadillo por encima del plato, con el pico mirando a Clawd."""
    k = size / DESIGN
    cr.select_font_face(BADGE_FAMILY, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    cr.set_font_size(11 * k)
    lines = text.split("\n")
    ext = [cr.text_extents(l) for l in lines]
    fe = cr.font_extents()
    line_h = fe[2]
    w = max(e.width for e in ext) + 20 * k
    h = line_h * len(lines) + 14 * k
    tip = 7 * k
    x, y = cx - w / 2, bottom - tip - h

    cr.set_source_rgba(0.16, 0.16, 0.18, 0.92)
    r = 11 * k
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()
    cr.fill()
    cr.move_to(cx - 6 * k, y + h)
    cr.line_to(cx + 6 * k, y + h)
    cr.line_to(cx, y + h + tip)
    cr.close_path()
    cr.fill()

    cr.set_source_rgb(1, 1, 1)
    for i, (line, e) in enumerate(zip(lines, ext)):
        cr.move_to(cx - e.width / 2 - e.x_bearing, y + 7 * k + fe[0] + i * line_h)
        cr.show_text(line)


# ─────────────────────────────────────────────────────────────
# Estado en disco
# ─────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────
# Volcado a PNG (sin pantalla)
# ─────────────────────────────────────────────────────────────

# El encuadre de docs/mascota-flotante.png, para poder comparar píxel a píxel.
REF_SCALE = 6
REF_W, REF_H = 730, 862
REF_PLATE_X, REF_PLATE_Y = 76.5, 77.5          # esquina del cuadrado, en píxeles


def write_png(path: str, data, night: bool, stale: bool = False,
              scale: int = REF_SCALE) -> None:
    w = round(REF_W * scale / REF_SCALE)
    h = round(REF_H * scale / REF_SCALE)
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(surface)
    cr.scale(scale, scale)
    cr.translate(REF_PLATE_X / REF_SCALE, REF_PLATE_Y / REF_SCALE)
    draw_pet(cr, data, night, size=DESIGN, stale=stale)
    surface.write_to_png(path)


# ─────────────────────────────────────────────────────────────
# La ventana
# ─────────────────────────────────────────────────────────────

import gi                                                          # noqa: E402

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")       # sin fijarlo se cuela Gdk 4.0 y choca
from gi.repository import Gdk, GLib, Gtk                           # noqa: E402

WIN_W, WIN_H = 200, 192          # mismo lienzo que la ventana de macOS
EDGE_MARGIN = 24                 # separación al borde al colocarla por defecto


def is_wayland() -> bool:
    """En Wayland una app no puede colocarse sola: `move()` se ignora."""
    display = Gdk.Display.get_default()
    name = display.get_name().lower() if display else ""
    return "wayland" in name or os.environ.get("XDG_SESSION_TYPE") == "wayland"


class PetWindow(Gtk.Window):
    def __init__(self, hub, on_quit=None):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.hub = hub
        self.on_quit = on_quit
        self._poke_until = 0.0
        self._bob = -BOB
        self._save_id = 0

        self.set_app_paintable(True)          # dibujamos nosotros el fondo
        self.set_decorated(False)             # sin marco ni barra de título
        self.set_keep_above(True)             # siempre encima
        self.set_skip_taskbar_hint(True)      # no sale en el conmutador
        self.set_skip_pager_hint(True)
        self.stick()                          # en todos los escritorios
        self.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        self.set_title("Claude Pet")
        self.set_default_size(WIN_W, WIN_H)

        screen = self.get_screen()            # transparencia real
        visual = screen.get_rgba_visual()
        self.composited = visual is not None
        if self.composited:
            self.set_visual(visual)

        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK
                        | Gdk.EventMask.POINTER_MOTION_MASK
                        | Gdk.EventMask.ENTER_NOTIFY_MASK
                        | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.connect("draw", self.on_draw)
        self.connect("button-press-event", self.on_click)
        self.connect("configure-event", self.on_configure)

        self.menu = self._build_menu()
        self._restore_position()
        GLib.timeout_add(1700, self._breathe)
        hub.subscribe(self._on_data)

    # ── Menú ─────────────────────────────────────────────────
    def _build_menu(self) -> Gtk.Menu:
        menu = Gtk.Menu()
        for label, handler in (
            ("Ocultar del escritorio", lambda *_: self.hide_pet()),
            ("Actualizar ahora", lambda *_: self.hub.refresh(force=True)),
            ("Traer a esta pantalla", lambda *_: self.recenter()),
        ):
            item = Gtk.MenuItem(label=label)
            item.connect("activate", handler)
            menu.append(item)
        menu.append(Gtk.SeparatorMenuItem())
        quit_item = Gtk.MenuItem(label="Salir de Claude Pet")
        quit_item.connect("activate", lambda *_: (self.on_quit or Gtk.main_quit)())
        menu.append(quit_item)
        menu.show_all()
        return menu

    # ── Colocación ───────────────────────────────────────────
    def _default_position(self) -> tuple[int, int]:
        """Abajo a la derecha del monitor principal, a 24 px del borde."""
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() or display.get_monitor(0)
        area = monitor.get_workarea()
        return (area.x + area.width - WIN_W - EDGE_MARGIN,
                area.y + area.height - WIN_H - EDGE_MARGIN)

    def _on_any_monitor(self, x: int, y: int) -> bool:
        display = Gdk.Display.get_default()
        for i in range(display.get_n_monitors()):
            a = display.get_monitor(i).get_workarea()
            if a.x <= x < a.x + a.width and a.y <= y < a.y + a.height:
                return True
        return False

    def _restore_position(self) -> None:
        state = load_state()
        x, y = state.get("x"), state.get("y")
        if not isinstance(x, int) or not isinstance(y, int) or not self._on_any_monitor(x, y):
            x, y = self._default_position()
        if not is_wayland():                  # en Wayland move() se ignora
            self.move(x, y)

    def recenter(self) -> None:
        x, y = self._default_position()
        if is_wayland():
            return
        self.move(x, y)
        self._remember(x, y)

    def on_configure(self, _w, event) -> bool:
        # En Wayland el cliente no sabe dónde está: `configure-event` siempre
        # trae (0, 0). Guardar eso no es guardar la posición, es pisarla con
        # una mentira que luego colocaría la mascota en la esquina si la
        # siguiente sesión fuese X11. Mejor conservar lo que hubiera.
        if is_wayland():
            return False
        if self._save_id:
            GLib.source_remove(self._save_id)
        # Pequeño debounce: al arrastrar llegan muchísimos eventos.
        self._save_id = GLib.timeout_add(400, self._remember, event.x, event.y)
        return False

    def _remember(self, x: int, y: int) -> bool:
        self._save_id = 0
        state = load_state()
        state.update({"x": int(x), "y": int(y)})
        save_state(state)
        return False                          # no repetir

    # ── Visibilidad ──────────────────────────────────────────
    def show_pet(self) -> None:
        state = load_state()
        state["pet_visible"] = True
        save_state(state)
        self.show_all()
        self.present()

    def hide_pet(self) -> None:
        state = load_state()
        state["pet_visible"] = False
        save_state(state)
        self.hide()

    # ── Datos y animación ────────────────────────────────────
    def _on_data(self, data, _changed) -> None:
        self.set_tooltip_text(self._tooltip(data))
        self.queue_draw()

    def _tooltip(self, data) -> str:
        if data is None:
            return usage.empty_reason()
        parts = [f"Sesión {data.session_pct}%"]
        if data.weekly is not None:
            parts.append(f"Semana {data.week_pct}%")
        line = " · ".join(parts)
        age = _ago(data.age)
        if data.is_stale and usage.claude_code_active():
            return f"{line}\n⚠︎ dato de hace {age}, puede estar viejo"
        return f"{line}\nhace {age}"

    def _breathe(self) -> bool:
        self._bob = BOB if self._bob < 0 else -BOB
        self.queue_draw()
        return True

    def poke(self) -> None:
        """Saluda. De paso relee los archivos, que es gratis."""
        self._poke_until = GLib.get_monotonic_time() / 1e6 + POKE_SECONDS
        self.hub.refresh(force=True)
        self.queue_draw()
        GLib.timeout_add(int(POKE_SECONDS * 1000), self._end_poke)

    def _end_poke(self) -> bool:
        self._poke_until = 0.0
        self.queue_draw()
        return False

    @property
    def _poking(self) -> bool:
        return GLib.get_monotonic_time() / 1e6 < self._poke_until

    # ── Eventos ──────────────────────────────────────────────
    def on_click(self, _w, event) -> bool:
        if event.button == 3:
            self.menu.popup_at_pointer(event)
            return True
        if event.button == 1:
            self.poke()
            # El arrastre lo hace el compositor: funciona también en Wayland.
            self.begin_move_drag(event.button, int(event.x_root), int(event.y_root),
                                 event.time)
            return True
        return False

    # ── Pintura ──────────────────────────────────────────────
    def on_draw(self, _w, cr) -> bool:
        cr.set_operator(cairo.OPERATOR_SOURCE)
        if self.composited:
            cr.set_source_rgba(0, 0, 0, 0)
        else:                                  # sin compositor no hay transparencia
            cr.set_source_rgb(0.13, 0.13, 0.14)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)

        data = self.hub.data
        stale = bool(data and data.is_stale and usage.claude_code_active())
        w = self.get_allocated_width()
        cr.save()
        cr.translate((w - DESIGN) / 2, BUBBLE_H)
        poking = self._poking
        draw_pet(cr, data, is_night(), size=DESIGN, stale=stale,
                 bob=self._bob - (0.5 if poking else 0),
                 eyes="happy" if poking else "open",
                 mouth=4 if poking else 0)
        if poking:
            _bubble(cr, DESIGN / 2, -3, DESIGN, self._greeting(data))
        cr.restore()
        return False

    def _greeting(self, data) -> str:
        if data is None:
            return "aún no hay cifras"
        return f"{data.session_pct}% de sesión\n{data.week_pct}% de semana"


def _ago(seconds: float) -> str:
    seconds = int(max(0, seconds))
    if seconds < 60:
        return f"{seconds} s"
    if seconds < 3600:
        return f"{seconds // 60} min"
    if seconds < 86400:
        return f"{seconds // 3600} h"
    return f"{seconds // 86400} d"
