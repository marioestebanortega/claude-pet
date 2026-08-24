"""
Arranque: bandeja y mascota sobre un solo `Gtk.main()`.

Vive aparte de `tray.py` porque la mascota necesita Cairo y la bandeja no: así
`--no-pet` sigue arrancando en una máquina donde falte `python3-gi-cairo`.
"""
from __future__ import annotations

import fcntl
import os
import sys
import tempfile

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

from .hub import Hub  # noqa: E402

APP_ID = "claudepet"
_lock = None                                   # vivo mientras dure el proceso


def _single_instance() -> bool:
    """Un solo Claude Pet a la vez.

    Sin esto, abrirlo desde la lista de aplicaciones cuando ya arrancó al
    iniciar sesión deja dos iconos idénticos en la bandeja.
    """
    global _lock
    run = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
    # O_NOFOLLOW y sin O_TRUNC a propósito: si esto cae en /tmp (porque no hay
    # XDG_RUNTIME_DIR), otro usuario de la máquina podría dejar ahí un symlink
    # a un archivo nuestro y hacérnoslo truncar al abrirlo.
    try:
        fd = os.open(os.path.join(run, "claudepet.lock"),
                     os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    except OSError:
        return True                            # sin candado, pero que arranque
    _lock = os.fdopen(fd, "r+")
    try:
        fcntl.flock(_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def run(show_tray: bool = True, show_pet: bool | None = None) -> int:
    """`show_pet` a None = lo que diga el estado guardado."""
    if not _single_instance():
        print("Claude Pet ya está abierto: mira el icono de la bandeja.")
        return 0

    # Sin esto la bandeja titula el applet «__main__.py», y GNOME no lo asocia
    # con claudepet.desktop.
    GLib.set_prgname(APP_ID)
    GLib.set_application_name("Claude Pet")

    hub = Hub()
    pet = tray = None

    if show_pet is not False:
        from . import pet as petmod
        if show_pet is None:
            show_pet = petmod.load_state().get("pet_visible", True)
        pet = petmod.PetWindow(hub, on_quit=Gtk.main_quit)

    if show_tray:
        from .tray import Tray
        try:
            tray = Tray(hub, pet=pet, on_quit=Gtk.main_quit)
        except RuntimeError as exc:
            if pet is None:
                print(f"No pude arrancar el applet: {exc}", file=sys.stderr)
                return 1
            print(f"Sigo solo con la mascota: {exc}", file=sys.stderr)

    if pet is not None:
        # Conectar antes de mostrar: si no, la casilla de la bandeja nace
        # desmarcada aunque la mascota esté a la vista.
        pet.connect("hide", lambda *_: tray and tray.sync_pet_item())
        pet.connect("show", lambda *_: tray and tray.sync_pet_item())
        if show_pet:
            pet.show_pet()
        elif tray is not None:
            tray.sync_pet_item()

    if tray is None and pet is None:
        print("No hay nada que enseñar: ni bandeja ni mascota.", file=sys.stderr)
        return 1

    hub.start()
    Gtk.main()
    return 0
