#!/usr/bin/env python3
"""
Construye claudepet_<version>_all.deb.

Se escribe a mano el formato `ar` en vez de llamar a dpkg-deb, para poder
generar y verificar el paquete desde cualquier sistema, también un Mac.
Un .deb son tres miembros ar: debian-binary, control.tar.gz y data.tar.gz.
"""
from __future__ import annotations

import io
import os
import sys
import tarfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
VERSION = "1.2"
PKG = "claudepet"

CONTROL = f"""Package: {PKG}
Version: {VERSION}
Section: utils
Priority: optional
Architecture: all
Depends: python3 (>= 3.9), python3-gi, python3-gi-cairo, gir1.2-gtk-3.0, gir1.2-ayatanaappindicator3-0.1 | gir1.2-appindicator3-0.1
Maintainer: Mario Ortega <maes0186@gmail.com>
Description: Mascota que vigila tu consumo de Claude Code
 Applet de bandeja que muestra cuanta cuota de Claude Code llevas gastada,
 leyendola de los archivos locales que el propio Claude Code escribe. No
 consume cuota, no usa red y no necesita ninguna clave de API.
 .
 Soporta tanto los planes por ventanas de tiempo (Pro, Max) como los
 medidos en dinero (Team, Enterprise), incluidos el gasto y los creditos
 mensuales.
 .
 Incluye ademas la mascota flotante: una ventana sin marco, siempre encima
 del escritorio, con los anillos de consumo y Clawd dentro.
"""

LAUNCHER = """#!/bin/sh
# Lanzador de Claude Pet
PYTHONPATH="/usr/lib/claudepet${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONPATH
exec python3 -m claudepet "$@"
"""

DESKTOP = """[Desktop Entry]
Type=Application
Name=Claude Pet
Comment=Vigila tu consumo de Claude Code
Exec=claudepet
Icon=claudepet
Terminal=false
Categories=Utility;Development;
Keywords=claude;usage;quota;
"""


def ar_member(name: str, data: bytes, mtime: int) -> bytes:
    header = (f"{name:<16}{mtime:<12}{0:<6}{0:<6}{'100644':<8}{len(data):<10}`\n").encode()
    padding = b"\n" if len(data) % 2 else b""
    return header + data + padding


def tar_gz(entries: list[tuple[str, bytes, int]], mtime: int) -> bytes:
    """entries: (ruta, contenido, modo). Crea los directorios intermedios."""
    buf = io.BytesIO()
    seen: set[str] = set()
    with tarfile.open(fileobj=buf, mode="w:gz", format=tarfile.GNU_FORMAT) as tar:
        for path, blob, mode in entries:
            parts = path.strip("./").split("/")
            for i in range(1, len(parts)):
                d = "./" + "/".join(parts[:i])
                if d in seen:
                    continue
                seen.add(d)
                info = tarfile.TarInfo(d)
                info.type, info.mode, info.mtime = tarfile.DIRTYPE, 0o755, mtime
                tar.addfile(info)
            info = tarfile.TarInfo("./" + "/".join(parts))
            info.size, info.mode, info.mtime = len(blob), mode, mtime
            tar.addfile(info, io.BytesIO(blob))
    return buf.getvalue()


def build(out_dir: str = os.path.join(os.path.dirname(HERE), "dist")) -> str:
    sys.path.insert(0, HERE)
    from claudepet import sprite

    mtime = int(os.environ.get("SOURCE_DATE_EPOCH") or time.time())
    data: list[tuple[str, bytes, int]] = []

    # El paquete Python
    pkg_dir = os.path.join(HERE, "claudepet")
    for name in sorted(os.listdir(pkg_dir)):
        if not name.endswith(".py"):
            continue
        with open(os.path.join(pkg_dir, name), "rb") as f:
            data.append((f"usr/lib/claudepet/claudepet/{name}", f.read(), 0o644))

    # El hook de statusLine vive en la raíz del repo, fuera de linux/, así que
    # no lo recoge el recorrido de arriba. Sin él, quien instale solo el .deb se
    # queda con ~/.claude.json como única fuente, que se refresca muy poco.
    with open(os.path.join(os.path.dirname(HERE), "statusline-pet.py"), "rb") as f:
        data.append(("usr/lib/claudepet/statusline-pet.py", f.read(), 0o755))

    data.append(("usr/bin/claudepet", LAUNCHER.encode(), 0o755))
    data.append(("usr/share/applications/claudepet.desktop", DESKTOP.encode(), 0o644))
    for px in (48, 64, 128):
        icon = sprite.render(cell=max(1, px // 11))
        data.append((f"usr/share/icons/hicolor/{px}x{px}/apps/claudepet.png", icon, 0o644))

    control_tar = tar_gz([("control", CONTROL.encode(), 0o644)], mtime)
    data_tar = tar_gz(data, mtime)

    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{PKG}_{VERSION}_all.deb")
    with open(out, "wb") as f:
        f.write(b"!<arch>\n")
        f.write(ar_member("debian-binary", b"2.0\n", mtime))
        f.write(ar_member("control.tar.gz", control_tar, mtime))
        f.write(ar_member("data.tar.gz", data_tar, mtime))
    return out


if __name__ == "__main__":
    path = build()
    print(f"📦 {path}  ({os.path.getsize(path) / 1024:.0f} KB)")
    print()
    print("Para instalarlo en Ubuntu:")
    print(f"    sudo apt install ./{os.path.basename(path)}")
    print()
    print("apt resuelve solo python3-gi y el indicador de bandeja.")
