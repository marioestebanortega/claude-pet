"""
Arranque: bandeja y mascota sobre un solo bucle de mensajes.

El orden importa y no es negociable:

1. **Instancia única** antes que nada, para no hacer trabajo que habrá que tirar.
2. **Conciencia de DPI antes de crear ninguna ventana.** Después ya no vale: la
   primera ventana fija la escala del proceso.
3. La ventana oculta, que es de la que cuelgan el temporizador y el icono.
4. El `Hub`, que necesita el temporizador.
5. La mascota y la bandeja, que necesitan el `Hub`.
"""
from __future__ import annotations

import ctypes
import sys

from . import loop, notify
from . import win32 as w
from .hub import Hub
from .state import load_state

APP_ID = "ClaudePet"
CLASS_NAME = "ClaudePetOwner"
# `Local\` y no `Global\`: dos usuarios en la misma máquina tienen cada uno su
# mascota, que es lo suyo en una app de bandeja de un solo usuario.
MUTEX_NAME = r"Local\ClaudePet.SingleInstance"

_mutex = None                                  # vivo mientras dure el proceso


def _single_instance() -> bool:
    """Un solo Claude Pet a la vez.

    Sin esto, abrirlo desde el menú Inicio cuando ya arrancó al iniciar sesión
    deja dos iconos idénticos en la bandeja.

    Al chocar no se limita a imprimir un aviso —que en una app sin consola no lo
    lee nadie— sino que le pide a la instancia viva que se deje ver. En Windows
    11 los iconos nuevos de la bandeja acaban escondidos en el desbordamiento,
    así que «no ha pasado nada al abrirlo» es la duda número uno; enseñar la
    mascota es la respuesta visible.
    """
    global _mutex
    _mutex = w.CreateMutexW(None, False, MUTEX_NAME)
    if _mutex and ctypes.get_last_error() == w.ERROR_ALREADY_EXISTS:
        w.PostMessageW(w.HWND_BROADCAST, loop.WM_CLAUDEPET_SHOW, 0, 0)
        return False
    return True


def run(show_tray: bool = True, show_pet: bool | None = None) -> int:
    """`show_pet` a None = lo que diga el estado guardado."""
    if not _single_instance():
        print("Claude Pet ya está abierto: mira el icono de la bandeja.")
        return 0

    w.set_dpi_aware()
    w.set_app_id(APP_ID)

    window = loop.Window(CLASS_NAME, "Claude Pet")
    sched = loop.Scheduler(window.hwnd)

    hub = Hub(sched)
    hub.on_auto_notice = notify.notify        # aviso de la primera consulta sola
    hub.on_notify = notify.notify             # avisos al cruzar 50/70/90 %
    pet = tray = None

    if show_pet is not False:
        from . import pet as petmod
        if show_pet is None:
            show_pet = load_state().get("pet_visible", True)
        pet = petmod.PetWindow(hub, on_quit=loop.quit)

    if show_tray:
        from .tray import Tray
        try:
            tray = Tray(hub, window, pet=pet, on_quit=loop.quit)
        except OSError as exc:
            if pet is None:
                print(f"No pude poner el icono en la bandeja: {exc}",
                      file=sys.stderr)
                return 1
            print(f"Sigo solo con la mascota: {exc}", file=sys.stderr)

    def dispatch(msg: int, wparam: int, lparam: int):
        if tray is not None:
            got = tray.on_message(msg, wparam, lparam)
        else:
            got = sched.handle(msg, wparam, lparam)
            if got is None and msg == loop.WM_CLAUDEPET_SHOW and pet is not None:
                pet.show_pet()
                pet.recenter()
                got = 0
        if msg == w.WM_DESTROY:
            loop.quit()
        return got

    window.on_message = dispatch

    if pet is not None and show_pet:
        pet.show_pet()

    if tray is None and pet is None:
        print("No hay nada que enseñar: ni bandeja ni mascota.", file=sys.stderr)
        return 1

    hub.start()
    try:
        return loop.run()
    finally:
        # Sin el NIM_DELETE queda un icono fantasma en la bandeja hasta que el
        # usuario pasa el ratón por encima.
        if tray is not None:
            tray.dispose()
        if pet is not None:
            pet.dispose()
