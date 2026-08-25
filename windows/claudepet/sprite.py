"""
Clawd en pixel-art y un escritor de PNG mínimo.

El PNG se genera con zlib y struct, sin Pillow ni cairo: el icono de bandeja
tiene que poder dibujarse aunque el AppImage no lleve nada más dentro.
La rejilla de 11 × 8 sale de `clawd.svg` de la extensión oficial de Claude Code.
"""
from __future__ import annotations

import struct
import zlib

COLS, ROWS = 11, 8
BRAND = 0xD97757

# Cuerpo sin los bracitos: van aparte para poder moverlos solos.
BODY = [
    ".#########.",
    ".#########.",
    ".#.#####.#.",   # ojos en las columnas 2 y 8
    ".#########.",
    ".#########.",
    ".#########.",
    ".#.#...#.#.",   # patas en las columnas 1, 3, 7 y 9
    ".#.#...#.#.",
]
ARM_ROWS = (2, 3)
EYE_COLS = (2, 8)

# Gorrito de dormir: cuerpo azul y ribete claro.
CAP_BODY = ["...........", "....#####..", "..######...", "..........."]
CAP_TRIM = ["........##.", "...........", "...........", ".#########."]
CAP_COLOR, CAP_TRIM_COLOR = 0x4C63C9, 0xEDEDF0


# ─────────────────────────────────────────────────────────────
# PNG
# ─────────────────────────────────────────────────────────────

def _chunk(tag: bytes, data: bytes) -> bytes:
    return (struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


def png_rgba(rows: list[list[tuple[int, int, int, int]]]) -> bytes:
    """Codifica una matriz de píxeles RGBA como PNG."""
    height, width = len(rows), len(rows[0])
    raw = b"".join(b"\x00" + bytes(v for px in row for v in px) for row in rows)
    return (b"\x89PNG\r\n\x1a\n"
            + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + _chunk(b"IDAT", zlib.compress(raw, 9))
            + _chunk(b"IEND", b""))


def _rgb(value: int) -> tuple[int, int, int]:
    return ((value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF)


# ─────────────────────────────────────────────────────────────
# Composición
# ─────────────────────────────────────────────────────────────

def body_grid(eyes: str = "open", mouth: int = 0) -> list[list[bool]]:
    g = [[ch == "#" for ch in row] for row in BODY]
    if eyes == "closed":
        for c in EYE_COLS:
            g[2][c] = True
    elif eyes == "wide":
        for c in EYE_COLS:
            g[1][c] = False
    elif eyes == "happy":
        g[2][2] = g[2][3] = g[2][7] = g[2][8] = False

    if mouth == 1:
        g[4][5] = False
    elif mouth == 2:
        for c in range(4, 7):
            g[4][c] = False
    elif mouth == 3:
        for c in range(4, 7):
            g[4][c] = g[5][c] = False
    elif mouth == 4:                       # sonrisa ∪
        g[4][3] = g[4][7] = False
        for c in range(4, 7):
            g[5][c] = False
    return g


def render_rgba(color: int = BRAND, night: bool = False, cell: int = 4,
                eyes: str = "open", mouth: int = 0) -> list[list[tuple[int, int, int, int]]]:
    """Devuelve la matriz RGBA de Clawd, sin codificar.

    Existe aparte de `render()` porque en Windows este mismo dibujo alimenta a
    dos consumidores que no quieren un PNG: el HICON de la bandeja, que se
    construye con `CreateDIBSection` sobre los píxeles crudos, y el `.ico` del
    acceso directo. Codificar para volver a decodificar sería absurdo.
    """
    cap_rows = len(CAP_BODY) - 1 if night else 0     # el ala se solapa con la cabeza
    total_rows = ROWS + cap_rows
    w, h = COLS * cell, total_rows * cell
    canvas = [[(0, 0, 0, 0)] * w for _ in range(h)]

    def put(col: int, row: int, rgb: tuple[int, int, int]) -> None:
        if not (0 <= col < COLS and 0 <= row < total_rows):
            return
        for y in range(row * cell, (row + 1) * cell):
            for x in range(col * cell, (col + 1) * cell):
                canvas[y][x] = (*rgb, 255)

    skin = _rgb(color)
    grid = body_grid(eyes, mouth)
    for r, line in enumerate(grid):
        for c, on in enumerate(line):
            if on:
                put(c, r + cap_rows, skin)
    for r in ARM_ROWS:                                # bracitos laterales
        put(0, r + cap_rows, skin)
        put(COLS - 1, r + cap_rows, skin)

    if night:
        for layer, tone in ((CAP_BODY, CAP_COLOR), (CAP_TRIM, CAP_TRIM_COLOR)):
            for r, line in enumerate(layer):
                for c, ch in enumerate(line):
                    if ch == "#":
                        put(c, r, _rgb(tone))

    return canvas


def render(color: int = BRAND, night: bool = False, cell: int = 4,
           eyes: str = "open", mouth: int = 0) -> bytes:
    """Devuelve un PNG con Clawd. Con `night`, lleva el gorrito puesto."""
    return png_rgba(render_rgba(color=color, night=night, cell=cell,
                                eyes=eyes, mouth=mouth))


# ─────────────────────────────────────────────────────────────
# Windows: lienzo cuadrado y .ico
# ─────────────────────────────────────────────────────────────

def render_square(px: int, color: int = BRAND, night: bool = False,
                  eyes: str = "open", mouth: int = 0
                  ) -> list[list[tuple[int, int, int, int]]]:
    """Clawd centrado en un lienzo cuadrado de `px` × `px`, transparente alrededor.

    La rejilla del sprite es de 11 × 8, o sea que `render_rgba()` da algo
    apaisado. A un tema de iconos de Linux eso le da igual; a Windows no: tanto
    el `.ico` como el HICON de la bandeja esperan una imagen cuadrada, y una
    apaisada sale estirada.

    El tamaño de celda es entero (`px // COLS`) a propósito: el pixel-art solo se
    ve nítido si cada celda cae justa en la rejilla de píxeles. Con 16 px salen
    celdas de 1 px, que es exactamente el dibujo original.
    """
    cell = max(1, px // COLS)              # COLS (11) ≥ filas, así que vale para los dos ejes
    art = render_rgba(color=color, night=night, cell=cell, eyes=eyes, mouth=mouth)
    h, w = len(art), len(art[0]) if art else 0
    ox, oy = (px - w) // 2, (px - h) // 2
    canvas = [[(0, 0, 0, 0)] * px for _ in range(px)]
    for y, line in enumerate(art):
        ty = oy + y
        if not (0 <= ty < px):
            continue
        row = canvas[ty]
        for x, pixel in enumerate(line):
            tx = ox + x
            if 0 <= tx < px and pixel[3]:
                row[tx] = pixel
    return canvas


def ico(sizes: tuple[int, ...] = (16, 32, 48, 64, 128, 256), **kwargs) -> bytes:
    """Empaqueta varios tamaños de Clawd en un `.ico`.

    Se escribe a mano con `struct`, igual que el `.deb` se escribe a mano en vez
    de llamar a `dpkg-deb`: así el icono se puede generar y comprobar desde
    cualquier sistema, también un Mac.

    Windows admite PNG dentro de un `.ico` desde Vista, así que no hace falta
    convertir a BMP con su máscara AND —que además obliga a duplicar cada fila
    y a alinearla a 4 bytes—. El 256 se codifica como 0 en la cabecera, que es
    como el formato dice «doscientos cincuenta y seis».
    """
    blobs = [png_rgba(render_square(px, **kwargs)) for px in sizes]
    offset = 6 + 16 * len(blobs)
    head = struct.pack("<HHH", 0, 1, len(blobs))     # reservado, tipo 1 = icono, cuántos
    entries = b""
    for px, blob in zip(sizes, blobs):
        entries += struct.pack("<BBBBHHII",
                               px & 0xFF, px & 0xFF,  # 256 → 0
                               0, 0,                  # sin paleta, reservado
                               1, 32,                 # planos, bits por píxel
                               len(blob), offset)
        offset += len(blob)
    return head + entries + b"".join(blobs)
