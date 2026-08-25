#!/usr/bin/env python3
"""
Construye `dist/ClaudePet-<version>-windows.zip`.

Es el equivalente del `.deb` de Ubuntu, pero mucho más corto, porque en Windows
no existe un formato de paquete que se instale sin administrador: MSI y MSIX
instalan por máquina (o sea, contraseña) y MSIX además pide un certificado de
firma. Así que el «paquete» es un zip portable con el instalador de PowerShell
dentro.

Se usa `zipfile` de la biblioteca estándar, así que —igual que `build-deb.py`,
que escribe el formato `ar` a mano— esto se puede generar y comprobar desde
cualquier sistema, también un Mac.

Las fechas salen de `SOURCE_DATE_EPOCH` o del último commit, para que dos
compilaciones del mismo estado den el mismo archivo en vez de depender del reloj.
"""
from __future__ import annotations

import os
import sys
import time
import zipfile

VERSION = "1.0"

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DIST = os.path.join(REPO, "dist")

LEEME = """Claude Pet para Windows
=======================

1) Desbloquea los archivos. Windows le pone la Marca de la Web a todo lo que
   sale de un .zip descargado, y con ella PowerShell se niega a ejecutar el
   instalador. Es el equivalente exacto del `xattr -dr com.apple.quarantine`
   que hace falta en macOS:

     Unblock-File -Path .\\*.ps1

2) Instala. Solo para tu usuario: no pide administrador en ningun momento.

     powershell -ExecutionPolicy Bypass -File .\\install-windows.ps1

   El -ExecutionPolicy Bypass tampoco es opcional: el valor por defecto en
   Windows 11 es Restricted, que no deja ejecutar ningun script, ni siquiera
   uno local.

   Si no tienes Python, el instalador lo pone el mismo con winget, tambien
   en ambito de usuario.

3) Para quitarlo:

     powershell -ExecutionPolicy Bypass -File .\\install-windows.ps1 off

Que necesita y que toca: mira windows\\README.md e INSTALAR.md.
"""


def _stamp() -> tuple:
    """Fecha reproducible, en el formato que quiere `zipfile`."""
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if not epoch:
        try:
            import subprocess
            out = subprocess.check_output(
                ["git", "-C", REPO, "log", "-1", "--format=%ct"],
                stderr=subprocess.DEVNULL)
            epoch = out.decode().strip()
        except Exception:
            epoch = "1700000000"
    return time.gmtime(int(epoch))[:6]


def main() -> int:
    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, f"ClaudePet-{VERSION}-windows.zip")
    stamp = _stamp()

    # El icono se genera aquí para que quien reciba el zip tenga un paso menos,
    # y porque `sprite.ico()` funciona en cualquier sistema.
    sys.path.insert(0, HERE)
    from claudepet import sprite
    icono = sprite.ico()

    piezas: list[tuple[str, bytes]] = []
    paquete = os.path.join(HERE, "claudepet")
    for name in sorted(os.listdir(paquete)):
        if not name.endswith(".py"):
            continue
        with open(os.path.join(paquete, name), "rb") as f:
            piezas.append((f"claudepet/{name}", f.read()))

    # El hook vive en la raíz del repo, no dentro de `windows/`: es el único
    # archivo de código que comparten las tres plataformas.
    with open(os.path.join(REPO, "statusline-pet.py"), "rb") as f:
        piezas.append(("statusline-pet.py", f.read()))
    with open(os.path.join(REPO, "install-windows.ps1"), "rb") as f:
        piezas.append(("install-windows.ps1", f.read()))
    with open(os.path.join(HERE, "README.md"), "rb") as f:
        piezas.append(("README.md", f.read()))
    piezas.append(("claudepet.ico", icono))
    piezas.append(("LEEME.txt", LEEME.encode("utf-8")))

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name, blob in piezas:
            info = zipfile.ZipInfo(name, date_time=stamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, blob)

    print(f"escrito {out} ({os.path.getsize(out) // 1024} KB, "
          f"{len(piezas)} archivos)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
