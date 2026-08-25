"""
El dibujo de la mascota: un rasterizador con antialiasing, escrito a mano.

Windows no trae nada parecido a Cairo. Las opciones eran GDI (sin suavizado en
arcos: círculos dentados), GDI+ (bien, pero son veinticinco enlaces más de
ctypes con su `GpStatus`, su `GdiplusStartup` y la trampa conocida del relleno
extra de `GdipMeasureString`) o escribirlo. Se escribió, porque todas las formas
del diseño son campos de distancia con signo y con eso el suavizado sale en
cuatro líneas — y porque es lo que ya hace este repo con el PNG y con el `.deb`.

La regla que mantiene esto manejable: **un solo bucle de píxeles**, `_fill`.
Recorre la caja envolvente de la forma, evalúa la distancia con signo en el
centro de cada píxel y compone. Un único sitio donde acertar con la mezcla.

El búfer es **BGRA premultiplicado**, que es lo que quiere `UpdateLayeredWindow`.
Componer sin premultiplicar deja un halo claro alrededor de cada borde suavizado
y es el fallo clásico de las ventanas en capas.

Como en Linux, el dibujo no sabe nada de la ventana: `--pet-png` lo vuelca a un
archivo sin necesitar pantalla, que es como se compara con
`docs/mascota-flotante.png` —la referencia exacta salida del código de macOS—.

Todas las medidas están en unidades de diseño con `size = 96`, igual que
`MascotView` en macOS y `pet.py` en Linux. Para dibujar más grande se escala
`size`, no las constantes.
"""
from __future__ import annotations

import ctypes
import math

from . import sprite, usage
from . import win32 as w

# ─────────────────────────────────────────────────────────────
# Proporciones — copiadas literales de linux/claudepet/pet.py:26-56,
# que a su vez salieron de MascotView y están verificadas contra la referencia.
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
# macOS usa SF Rounded y Linux pide «Ubuntu»; aquí, Segoe UI, que es la de
# Windows. Es la única diferencia visible entre las tres versiones.
BADGE_FAMILY = "Segoe UI"

BUBBLE_H = 66.0                            # hueco para el bocadillo, encima
DESIGN = 96.0
POKE_SECONDS = 2.8

# El encuadre de docs/mascota-flotante.png, para poder comparar píxel a píxel.
REF_SCALE = 6
REF_W, REF_H = 730, 862
REF_PLATE_X, REF_PLATE_Y = 76.5, 77.5


def _rgb(value: int) -> tuple[int, int, int]:
    return (value >> 16 & 0xFF, value >> 8 & 0xFF, value & 0xFF)


def is_night(hour: int | None = None) -> bool:
    """Gorrito entre las 18:00 y las 6:00. (Espejo de `tray._is_night`.)"""
    if hour is None:
        import datetime
        hour = datetime.datetime.now().hour
    return hour >= 18 or hour < 6


# ─────────────────────────────────────────────────────────────
# El lienzo
# ─────────────────────────────────────────────────────────────
class Canvas:
    """Un búfer BGRA premultiplicado, del tamaño exacto de la ventana."""

    __slots__ = ("w", "h", "buf")

    def __init__(self, width: int, height: int) -> None:
        self.w, self.h = int(width), int(height)
        self.buf = bytearray(self.w * self.h * 4)

    def clear(self) -> None:
        self.buf[:] = bytes(len(self.buf))

    def copy_from(self, other: "Canvas") -> None:
        """Un solo memcpy. Es lo que hace barato repintar solo a Clawd."""
        self.buf[:] = other.buf

    # ── El único bucle de píxeles ────────────────────────────
    def _fill(self, box: tuple[float, float, float, float], sdf,
              rgb: tuple[int, int, int], alpha: float) -> None:
        """Compone `rgb` con la cobertura que dé `sdf` dentro de la caja `box`.

        `sdf(x, y)` devuelve la distancia con signo al borde de la forma:
        negativa dentro, positiva fuera. La cobertura del píxel se aproxima con
        una rampa de un píxel de ancho, que es lo que hace Cairo por defecto y
        basta de sobra a estos tamaños.
        """
        if alpha <= 0:
            return
        x0 = max(0, int(math.floor(box[0])))
        y0 = max(0, int(math.floor(box[1])))
        x1 = min(self.w, int(math.ceil(box[2])))
        y1 = min(self.h, int(math.ceil(box[3])))
        if x0 >= x1 or y0 >= y1:
            return
        red, green, blue = rgb
        buf = self.w
        data = self.buf
        for py in range(y0, y1):
            fy = py + 0.5
            base = py * buf * 4
            for px in range(x0, x1):
                cov = 0.5 - sdf(px + 0.5, fy)
                if cov <= 0:
                    continue
                if cov > 1:
                    cov = 1.0
                a = cov * alpha
                inv = 1.0 - a
                i = base + px * 4
                # src-over premultiplicado: dst = src + dst · (1 − a)
                data[i] = int(blue * a + data[i] * inv)
                data[i + 1] = int(green * a + data[i + 1] * inv)
                data[i + 2] = int(red * a + data[i + 2] * inv)
                data[i + 3] = int(255 * a + data[i + 3] * inv)

    # ── Formas ───────────────────────────────────────────────
    def rect(self, x: float, y: float, width: float, height: float,
             rgb: tuple[int, int, int], alpha: float = 1.0) -> None:
        """Rectángulo alineado a los ejes. Sin suavizado a propósito: son las
        celdas del pixel-art de Clawd, y suavizarlas lo emborronaría."""
        x0, y0 = max(0, int(round(x))), max(0, int(round(y)))
        x1 = min(self.w, int(round(x + width)))
        y1 = min(self.h, int(round(y + height)))
        if x0 >= x1 or y0 >= y1:
            return
        red, green, blue = rgb
        if alpha >= 1.0:
            row = bytes((blue, green, red, 255)) * (x1 - x0)
            for py in range(y0, y1):
                i = (py * self.w + x0) * 4
                self.buf[i:i + len(row)] = row
            return
        self._fill((x0, y0, x1, y1), lambda _px, _py: -1.0, rgb, alpha)

    def disc(self, cx: float, cy: float, r: float,
             rgb: tuple[int, int, int], alpha: float = 1.0) -> None:
        self._fill((cx - r - 1, cy - r - 1, cx + r + 1, cy + r + 1),
                   lambda x, y: math.hypot(x - cx, y - cy) - r, rgb, alpha)

    def circle_edge(self, cx: float, cy: float, r: float, width: float,
                    rgb: tuple[int, int, int], alpha: float = 1.0) -> None:
        """El trazo de una circunferencia, centrado en el radio."""
        half = width / 2
        self._fill((cx - r - half - 1, cy - r - half - 1,
                    cx + r + half + 1, cy + r + half + 1),
                   lambda x, y: abs(math.hypot(x - cx, y - cy) - r) - half,
                   rgb, alpha)

    def arc(self, cx: float, cy: float, r: float, width: float,
            start: float, sweep: float, rgb: tuple[int, int, int],
            alpha: float = 1.0, round_caps: bool = True) -> None:
        """Un arco de `sweep` radianes desde `start`, en sentido horario.

        El corte angular es duro; los extremos redondeados se dibujan encima como
        dos discos, que además es exactamente lo que hace `LINE_CAP_ROUND`. Así
        el único borde sin suavizar queda tapado.
        """
        if sweep <= 0:
            return
        half = width / 2
        two_pi = 2 * math.pi
        full = sweep >= two_pi - 1e-6

        def sdf(x: float, y: float) -> float:
            radial = abs(math.hypot(x - cx, y - cy) - r) - half
            if full or radial > 0.5:
                return radial
            theta = (math.atan2(y - cy, x - cx) - start) % two_pi
            return radial if theta <= sweep else 1.0

        self._fill((cx - r - half - 1, cy - r - half - 1,
                    cx + r + half + 1, cy + r + half + 1), sdf, rgb, alpha)
        if round_caps and not full:
            for angle in (start, start + sweep):
                self.disc(cx + r * math.cos(angle), cy + r * math.sin(angle),
                          half, rgb, alpha)

    def capsule(self, x: float, y: float, width: float, height: float,
                rgb: tuple[int, int, int], alpha: float = 1.0,
                radius: float | None = None) -> None:
        r = height / 2 if radius is None else radius
        self._fill((x - 1, y - 1, x + width + 1, y + height + 1),
                   _round_rect_sdf(x, y, width, height, r), rgb, alpha)

    def capsule_edge(self, x: float, y: float, width: float, height: float,
                     stroke: float, rgb: tuple[int, int, int],
                     alpha: float = 1.0, radius: float | None = None) -> None:
        r = height / 2 if radius is None else radius
        inner = _round_rect_sdf(x, y, width, height, r)
        half = stroke / 2
        self._fill((x - 1 - half, y - 1 - half,
                    x + width + 1 + half, y + height + 1 + half),
                   lambda px, py: abs(inner(px, py)) - half, rgb, alpha)

    def tri(self, p0: tuple[float, float], p1: tuple[float, float],
            p2: tuple[float, float], rgb: tuple[int, int, int],
            alpha: float = 1.0) -> None:
        xs = (p0[0], p1[0], p2[0])
        ys = (p0[1], p1[1], p2[1])

        def edge(ax, ay, bx, by, px, py):
            return (bx - ax) * (py - ay) - (by - ay) * (px - ax)

        # Orientación, para que dé igual el orden en que vengan los vértices.
        sign = 1.0 if edge(*p0, *p1, *p2) >= 0 else -1.0
        # El producto cruzado vale «longitud del lado × distancia»: dividiendo
        # por la longitud queda una distancia de verdad, y la rampa de suavizado
        # mide un píxel como en el resto de las formas.
        lengths = [max(1e-6, math.hypot(b[0] - a[0], b[1] - a[1]))
                   for a, b in ((p0, p1), (p1, p2), (p2, p0))]

        def sdf(px: float, py: float) -> float:
            inside = min(sign * edge(*p0, *p1, px, py) / lengths[0],
                         sign * edge(*p1, *p2, px, py) / lengths[1],
                         sign * edge(*p2, *p0, px, py) / lengths[2])
            return -inside

        self._fill((min(xs) - 1, min(ys) - 1, max(xs) + 1, max(ys) + 1),
                   sdf, rgb, alpha)

    def text(self, x: float, y: float, mask: "TextMask",
             rgb: tuple[int, int, int], alpha: float = 1.0) -> None:
        """Pega una máscara de cobertura ya rasterizada por GDI."""
        red, green, blue = rgb
        ox, oy = int(round(x)), int(round(y))
        for row in range(mask.h):
            py = oy + row
            if not (0 <= py < self.h):
                continue
            line = row * mask.w
            base = py * self.w * 4
            for col in range(mask.w):
                cov = mask.cov[line + col]
                if not cov:
                    continue
                px = ox + col
                if not (0 <= px < self.w):
                    continue
                a = (cov / 255) * alpha
                inv = 1.0 - a
                i = base + px * 4
                self.buf[i] = int(blue * a + self.buf[i] * inv)
                self.buf[i + 1] = int(green * a + self.buf[i + 1] * inv)
                self.buf[i + 2] = int(red * a + self.buf[i + 2] * inv)
                self.buf[i + 3] = int(255 * a + self.buf[i + 3] * inv)

    # ── Salida ───────────────────────────────────────────────
    def to_png(self) -> bytes:
        """Des-premultiplica y reutiliza el escritor de PNG de `sprite.py`."""
        rows = []
        for py in range(self.h):
            base = py * self.w * 4
            row = []
            for px in range(self.w):
                i = base + px * 4
                a = self.buf[i + 3]
                if a == 0:
                    row.append((0, 0, 0, 0))
                    continue
                k = 255 / a
                row.append((min(255, int(self.buf[i + 2] * k)),
                            min(255, int(self.buf[i + 1] * k)),
                            min(255, int(self.buf[i] * k)), a))
            rows.append(row)
        return sprite.png_rgba(rows)


def _round_rect_sdf(x: float, y: float, width: float, height: float, r: float):
    """Distancia con signo a un rectángulo de esquinas redondeadas."""
    hw, hh = width / 2, height / 2
    cx, cy = x + hw, y + hh
    r = min(r, hw, hh)

    def sdf(px: float, py: float) -> float:
        dx = abs(px - cx) - (hw - r)
        dy = abs(py - cy) - (hh - r)
        if dx <= 0 and dy <= 0:
            return max(dx, dy) - r
        return math.hypot(max(dx, 0.0), max(dy, 0.0)) - r

    return sdf


# ─────────────────────────────────────────────────────────────
# Texto: máscaras de cobertura sacadas de GDI
# ─────────────────────────────────────────────────────────────
class TextMask:
    __slots__ = ("w", "h", "cov")

    def __init__(self, width: int, height: int, cov: bytearray) -> None:
        self.w, self.h, self.cov = width, height, cov


_masks: dict[tuple, TextMask] = {}


def text_mask(text: str, px: int, bold: bool = True,
              family: str = BADGE_FAMILY) -> TextMask:
    """Rasteriza `text` y devuelve su cobertura, un byte por píxel.

    Se pide `ANTIALIASED_QUALITY` y **no** `CLEARTYPE_QUALITY`: ClearType da una
    cobertura distinta por canal (es suavizado por subpíxel), y leída como un
    único alfa produce flecos de color en el texto del badge.

    Memorizado por `(texto, tamaño, negrita)`: el badge solo cambia cuando
    cambian las cifras, así que en la práctica se rasteriza una vez.
    """
    key = (text, px, bold, family)
    got = _masks.get(key)
    if got is not None:
        return got
    if not text:
        return TextMask(0, 0, bytearray())

    screen = w.GetDC(None)
    dc = w.CreateCompatibleDC(screen)
    font = old_font = hbm = old_bm = None
    try:
        font = w.CreateFontW(-int(px), 0, 0, 0, w.FW_BOLD if bold else w.FW_NORMAL,
                             0, 0, 0, w.DEFAULT_CHARSET, w.OUT_TT_PRECIS,
                             w.CLIP_DEFAULT_PRECIS, w.ANTIALIASED_QUALITY,
                             w.DEFAULT_PITCH, family)
        old_font = w.SelectObject(dc, font)

        rect = w.wintypes.RECT(0, 0, 0, 0)
        flags = w.DT_SINGLELINE | w.DT_NOPREFIX | w.DT_LEFT | w.DT_TOP
        w.DrawTextW(dc, text, -1, ctypes.byref(rect), flags | w.DT_CALCRECT)
        width, height = max(1, rect.right), max(1, rect.bottom)

        info = w.dib_header(width, height)
        bits = w.LPVOID()
        hbm = w.CreateDIBSection(dc, ctypes.byref(info), w.DIB_RGB_COLORS,
                                 ctypes.byref(bits), None, 0)
        if not hbm or not bits:
            return TextMask(0, 0, bytearray())
        old_bm = w.SelectObject(dc, hbm)
        # Texto blanco sobre negro opaco: el nivel de gris ES la cobertura.
        w.SetBkColor(dc, 0x000000)
        w.SetTextColor(dc, 0xFFFFFF)
        w.SetBkMode(dc, w.OPAQUE)
        rect = w.wintypes.RECT(0, 0, width, height)
        w.DrawTextW(dc, text, -1, ctypes.byref(rect), flags)

        raw = (ctypes.c_char * (width * height * 4)).from_address(bits.value)
        blob = bytes(raw)
        cov = bytearray(width * height)
        for index in range(width * height):
            cov[index] = blob[index * 4]        # cualquier canal vale: es gris
        mask = TextMask(width, height, cov)
        _masks[key] = mask
        return mask
    finally:
        if old_bm is not None:
            w.SelectObject(dc, old_bm)
        if hbm:
            w.DeleteObject(hbm)
        if old_font is not None:
            w.SelectObject(dc, old_font)
        if font:
            w.DeleteObject(font)
        w.DeleteDC(dc)
        w.ReleaseDC(None, screen)


# ─────────────────────────────────────────────────────────────
# Las piezas del diseño
# ─────────────────────────────────────────────────────────────
def _ring(cv: Canvas, cx: float, cy: float, radius: float,
          width: float, pct: int) -> None:
    """Pista tenue + arco de color, desde las 12 y en sentido horario."""
    cv.circle_edge(cx, cy, radius, width, (255, 255, 255), TRACK_ALPHA)
    if pct <= 0:
        return
    # Cada anillo se colorea por SU propio porcentaje, no por el humor global.
    color = _rgb(usage.MOOD_COLORS[usage.mood_for(pct)][0])
    cv.arc(cx, cy, radius, width, -math.pi / 2,
           2 * math.pi * min(pct, 100) / 100, color)


def _clawd(cv: Canvas, cx: float, cy: float, size: float, night: bool,
           bob: float, eyes: str, mouth: int, color: int) -> None:
    cell = size * CLAWD_W / sprite.COLS
    ox = cx - CANVAS_COLS * cell / 2 + cell * CLAWD_OFF_X
    oy = cy - CANVAS_ROWS * cell / 2 + cell * (CLAWD_OFF_Y + bob)

    def put(col: int, row: int, tone: int) -> None:
        cv.rect(ox + col * cell, oy + row * cell, cell + SEAM, cell + SEAM,
                _rgb(tone))

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


def _badge(cv: Canvas, cx: float, top: float, size: float,
           text: str, deep: int) -> None:
    k = size / DESIGN
    mask = text_mask(text, max(1, int(round(BADGE_FONT * k))), bold=True)
    height = mask.h + 2 * BADGE_PAD_Y * k
    width = mask.w + 2 * BADGE_PAD_X * k
    x = cx - width / 2

    cv.capsule(x, top, width, height, _rgb(deep))
    cv.capsule_edge(x, top, width, height, BADGE_EDGE_W * k,
                    (255, 255, 255), BADGE_EDGE_ALPHA)
    cv.text(cx - mask.w / 2, top + BADGE_PAD_Y * k, mask, (255, 255, 255))


def _mood_of(data, stale: bool) -> str:
    return "broken" if (data is None or stale) else usage.mood_for(data.worst)


def draw_dial(cv: Canvas, data, size: float = DESIGN, stale: bool = False, *,
              origin: tuple[float, float] = (0.0, 0.0)) -> None:
    """Plato + anillos + badge: todo lo que NO se mueve entre fotogramas.

    Está separado de `draw_mascot` porque es la mitad cara del dibujo —los
    anillos y el badge son casi todos los píxeles suavizados que hay— y solo
    cambia cuando cambian los datos. La ventana lo guarda en un lienzo aparte y
    por fotograma solo hace un memcpy y repinta a Clawd, que son noventa
    rectángulos opacos. Sin esto, animar la respiración costaría decenas de
    milisegundos cada 1,7 s para mover un bicho tres píxeles.
    """
    ox, oy = origin
    cx, cy = ox + size / 2, oy + size / 2
    mood = _mood_of(data, stale)

    # Plato
    cv.disc(cx, cy, size / 2 - size * PLATE_PAD, PLATE_RGB, PLATE_ALPHA)
    cv.circle_edge(cx, cy, size / 2 - size * PLATE_PAD, PLATE_EDGE_W * size / DESIGN,
                   (255, 255, 255), PLATE_EDGE_ALPHA)

    # Anillos: exterior la semana, interior la sesión. Si el plan solo separa
    # una dimensión, un único anillo del ancho del exterior.
    session = data.session_pct if data else 0
    week = data.week_pct if data else 0
    secondary = data is not None and data.has_secondary
    if secondary:
        _ring(cv, cx, cy, size / 2, size * OUTER_W, week)
        _ring(cv, cx, cy, size / 2 - size * INNER_INSET, size * INNER_W, session)
    else:
        _ring(cv, cx, cy, size / 2, size * OUTER_W, session)

    text = f"{session}/{week}%" if secondary else f"{session}%"
    if data is None:
        text = "0/0%"
    if stale:
        text = "⏱ " + text
    _badge(cv, cx, oy + size + BADGE_GAP * size / DESIGN, size, text,
           usage.MOOD_COLORS[mood][1])


def draw_mascot(cv: Canvas, data, night: bool, size: float = DESIGN,
                stale: bool = False, *, origin: tuple[float, float] = (0.0, 0.0),
                bob: float = -BOB, eyes: str = "open", mouth: int = 0,
                tinted: bool = False) -> None:
    """Solo Clawd: lo único que se mueve."""
    ox, oy = origin
    mood = _mood_of(data, stale)
    _clawd(cv, ox + size / 2, oy + size / 2, size, night, bob, eyes, mouth,
           usage.MOOD_COLORS[mood][0] if tinted else sprite.BRAND)


def draw_pet(cv: Canvas, data, night: bool, size: float = DESIGN,
             stale: bool = False, *, origin: tuple[float, float] = (0.0, 0.0),
             bob: float = -BOB, eyes: str = "open", mouth: int = 0,
             tinted: bool = False) -> None:
    """Plato + anillos + Clawd + badge, con la esquina del cuadrado en `origin`.

    Los anillos se salen de ese cuadrado medio grosor y el badge queda debajo,
    centrado. Es el mismo reparto que en Linux y en macOS.

    Aquí Clawd se pinta después del badge, y en Linux antes: da igual porque no
    se tocan —el badge cae fuera del cuadrado—, y este orden es el que permite
    cachear el plato entero en un lienzo aparte (ver `draw_dial`).
    """
    draw_dial(cv, data, size, stale, origin=origin)
    draw_mascot(cv, data, night, size, stale, origin=origin,
                bob=bob, eyes=eyes, mouth=mouth, tinted=tinted)


def draw_bubble(cv: Canvas, cx: float, bottom: float, size: float,
                text: str) -> None:
    """Bocadillo por encima del plato, con el pico mirando a Clawd."""
    k = size / DESIGN
    lines = text.split("\n")
    masks = [text_mask(line, max(1, int(round(11 * k))), bold=False)
             for line in lines]
    line_h = max((m.h for m in masks), default=0)
    width = max((m.w for m in masks), default=0) + 20 * k
    height = line_h * len(lines) + 14 * k
    tip = 7 * k
    x, y = cx - width / 2, bottom - tip - height

    cv.capsule(x, y, width, height, (41, 41, 46), 0.92, radius=11 * k)
    cv.tri((cx - 6 * k, y + height), (cx + 6 * k, y + height),
           (cx, y + height + tip), (41, 41, 46), 0.92)
    for index, mask in enumerate(masks):
        cv.text(cx - mask.w / 2, y + 7 * k + index * line_h, mask, (255, 255, 255))


# ─────────────────────────────────────────────────────────────
# Volcado a PNG (sin pantalla)
# ─────────────────────────────────────────────────────────────
def write_png(path: str, data, night: bool, stale: bool = False,
              scale: int = REF_SCALE) -> None:
    """Vuelca la mascota con el encuadre exacto de docs/mascota-flotante.png.

    Es la prueba que valida el rasterizador: si esto no se parece a la
    referencia, no hay que seguir con la ventana.
    """
    factor = scale / REF_SCALE
    cv = Canvas(round(REF_W * factor), round(REF_H * factor))
    # En Linux esto es `cr.scale(scale)` + `translate(REF_PLATE_X / REF_SCALE)`
    # y `size = DESIGN`; aquí no hay matriz de transformación, así que las dos
    # cosas se hacen a mano: el cuadrado mide `DESIGN × scale` píxeles y la
    # esquina cae en `REF_PLATE_X × factor`.
    draw_pet(cv, data, night, size=DESIGN * scale, stale=stale,
             origin=(REF_PLATE_X * factor, REF_PLATE_Y * factor))
    with open(path, "wb") as f:
        f.write(cv.to_png())
