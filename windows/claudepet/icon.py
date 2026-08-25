"""
El icono de la bandeja: Clawd y, debajo, el porcentaje de la sesión.

La bandeja de Windows **no admite texto al lado del icono**. En Linux el applet
llama a `ind.set_label("😺 25%")` y en macOS la barra de menús enseña lo mismo;
aquí no hay ningún equivalente, así que la cifra —que es el motivo de que la app
exista— se pinta dentro del propio icono, como hacen los medidores de batería y
de red.

El número se dibuja con una fuente de píxeles de 3 × 5 hecha a mano, y no con
GDI: a 16 píxeles un dígito rasterizado con antialiasing sale borroso, mientras
que uno de píxeles cae justo en la rejilla y queda nítido. De paso es el mismo
lenguaje visual que Clawd, que también es pixel-art.

Reparto sobre una rejilla de 16 unidades (que es lo que mide el icono al 100 %):
Clawd ocupa las 8 de arriba y los dígitos las 5 de abajo, con un hueco en medio.
Para tamaños mayores (24 px al 150 %, 32 px al 200 %) se escala con un tamaño de
celda entero, que es la única manera de que el pixel-art no se emborrone.
"""
from __future__ import annotations

import ctypes

from . import sprite
from . import win32 as w

# Fuente de píxeles de 3 × 5. Es el mínimo con el que un dígito sigue siendo
# inequívoco; con 3 × 4 el 8 y el 0 se confunden.
DIGITS = {
    "0": ("111", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("111", "001", "111", "100", "111"),
    "3": ("111", "001", "111", "001", "111"),
    "4": ("101", "101", "111", "001", "001"),
    "5": ("111", "100", "111", "001", "111"),
    "6": ("111", "100", "111", "101", "111"),
    "7": ("111", "001", "001", "001", "001"),
    "8": ("111", "101", "111", "101", "111"),
    "9": ("111", "101", "111", "001", "111"),
}
DIGIT_W, DIGIT_H = 3, 5

GRID = 16               # unidades de diseño: el icono al 100 %
CLAWD_ROWS = 8          # las de arriba
DIGIT_TOP = 11          # los dígitos empiezan aquí (deja un hueco de 3)


def _blank(size: int) -> bytearray:
    return bytearray(size * size * 4)


def _put(buf: bytearray, size: int, x: int, y: int, rgb: tuple[int, int, int]) -> None:
    if not (0 <= x < size and 0 <= y < size):
        return
    i = (y * size + x) * 4
    buf[i] = rgb[2]                       # el DIB es BGRA
    buf[i + 1] = rgb[1]
    buf[i + 2] = rgb[0]
    buf[i + 3] = 255


def _cell(buf: bytearray, size: int, col: int, row: int, unit: int,
          ox: int, oy: int, rgb: tuple[int, int, int]) -> None:
    for dy in range(unit):
        for dx in range(unit):
            _put(buf, size, ox + col * unit + dx, oy + row * unit + dy, rgb)


def _draw_digits(buf: bytearray, size: int, unit: int, text: str,
                 rgb: tuple[int, int, int]) -> None:
    """Los dígitos, centrados en la franja de abajo."""
    if not text:
        return
    width = (DIGIT_W * len(text) + (len(text) - 1)) * unit    # un hueco entre dígitos
    ox = (size - width) // 2
    oy = DIGIT_TOP * unit
    for index, ch in enumerate(text):
        glyph = DIGITS.get(ch)
        if glyph is None:
            continue
        base = index * (DIGIT_W + 1)
        for row, line in enumerate(glyph):
            for col, on in enumerate(line):
                if on == "1":
                    _cell(buf, size, base + col, row, unit, ox, oy, rgb)


def _draw_clawd(buf: bytearray, size: int, unit: int, color: int, night: bool) -> None:
    """Clawd arriba, con la misma rejilla de `sprite.py` para no duplicar el dibujo."""
    rgb = ((color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF)
    ox = (size - sprite.COLS * unit) // 2
    cap = len(sprite.CAP_BODY) - 1 if night else 0
    oy = 0

    def cell(col: int, row: int, tone: tuple[int, int, int]) -> None:
        _cell(buf, size, col, row, unit, ox, oy, tone)

    for row, line in enumerate(sprite.body_grid()):
        for col, on in enumerate(line):
            if on:
                cell(col, row + cap, rgb)
    for row in sprite.ARM_ROWS:
        cell(0, row + cap, rgb)
        cell(sprite.COLS - 1, row + cap, rgb)
    if night:
        for layer, tone in ((sprite.CAP_BODY, sprite.CAP_COLOR),
                            (sprite.CAP_TRIM, sprite.CAP_TRIM_COLOR)):
            for row, line in enumerate(layer):
                for col, ch in enumerate(line):
                    if ch == "#":
                        cell(col, row, ((tone >> 16) & 0xFF, (tone >> 8) & 0xFF,
                                        tone & 0xFF))


def pixels(size: int, color: int = sprite.BRAND, night: bool = False,
           percent: int | None = None, accent: int | None = None) -> bytearray:
    """El icono en BGRA, listo para un DIB. Sin datos, solo Clawd.

    `color` es el de Clawd y `accent` el de la cifra. Van separados por lo mismo
    que en Linux: allí el icono siempre lleva el naranja de marca y el humor
    viaja en la etiqueta de texto de al lado. Aquí no hay etiqueta, así que el
    humor se pinta en los dígitos — que además es donde se está mirando.
    """
    unit = max(1, size // GRID)
    buf = _blank(size)
    rgb = ((color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF)
    tone = rgb if accent is None else ((accent >> 16) & 0xFF,
                                       (accent >> 8) & 0xFF, accent & 0xFF)
    if percent is None:
        # Sin cifra, Clawd se dibuja a su tamaño natural y centrado, como en
        # Linux: no hay razón para dejarle sitio a un número que no existe.
        art = sprite.render_square(size, color=color, night=night)
        for y, line in enumerate(art):
            for x, pixel in enumerate(line):
                if pixel[3]:
                    _put(buf, size, x, y, pixel[:3])
        return buf
    _draw_clawd(buf, size, unit, color, night)
    _draw_digits(buf, size, unit, str(max(0, min(999, int(percent)))), tone)
    return buf


def hicon(size: int, color: int = sprite.BRAND, night: bool = False,
          percent: int | None = None, accent: int | None = None) -> int:
    """Construye un HICON en memoria. Quien llama tiene que destruirlo.

    El bitmap de color de un icono usa alfa **directo**, no premultiplicado como
    `UpdateLayeredWindow`. Aquí da igual porque el pixel-art solo tiene alfa 0 o
    255, y en los dos casos coinciden; pero conviene saberlo antes de suavizar
    ningún borde de este icono.
    """
    buf = pixels(size, color=color, night=night, percent=percent, accent=accent)
    hdc = w.GetDC(None)
    hbm_color = hbm_mask = 0
    try:
        info = w.dib_header(size, size)
        bits = w.LPVOID()
        hbm_color = w.CreateDIBSection(hdc, ctypes.byref(info), w.DIB_RGB_COLORS,
                                       ctypes.byref(bits), None, 0)
        if not hbm_color or not bits:
            return 0
        ctypes.memmove(bits, bytes(buf), len(buf))
        # Máscara AND toda a ceros: con un bitmap de color de 32 bits manda el
        # canal alfa, y la máscara solo tiene que no tapar nada.
        hbm_mask = w.CreateBitmap(size, size, 1, 1, None)
        if not hbm_mask:
            return 0
        ii = w.ICONINFO(1, 0, 0, hbm_mask, hbm_color)
        return int(w.CreateIconIndirect(ctypes.byref(ii)) or 0)
    finally:
        # `CreateIconIndirect` se queda con una copia, así que los bitmaps se
        # sueltan aquí mismo. No hacerlo es una fuga de dos objetos GDI por cada
        # refresco del icono, o sea unos cuantos miles al día.
        if hbm_color:
            w.DeleteObject(hbm_color)
        if hbm_mask:
            w.DeleteObject(hbm_mask)
        w.ReleaseDC(None, hdc)
