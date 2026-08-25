"""
Menús emergentes: los de la bandeja y el del clic derecho de la mascota.

Un `Gtk.Menu` es persistente y por eso la versión de Linux mantiene diez filas
reutilizables que va enseñando y escondiendo (`tray.py:74-117`). `TrackPopupMenu`
no funciona así: se construye el menú, se enseña y se destruye. Eso simplifica
bastante el puerto —desaparecen las filas reutilizables, el `show()/hide()` y los
`handler_block_by_func` de las casillas, porque el estado se lee al construir— y
a cambio obliga a tener cuidado con dos cosas, que es de lo que va este módulo:

- **Destruir el menú siempre.** Un HMENU que no se destruye es una fuga de
  objetos de usuario, y aquí se abre un menú cada vez que alguien clica.
- **El baile de la Q135788**: `SetForegroundWindow` antes de `TrackPopupMenu` y
  un `WM_NULL` después. Sin eso, el menú se queda abierto cuando el usuario
  clica fuera, que es el fallo más visible que puede tener una app de bandeja.
"""
from __future__ import annotations

from . import win32 as w

# Los identificadores empiezan en 1: `TPM_RETURNCMD` devuelve 0 cuando el
# usuario cancela con Esc o clicando fuera, así que un ítem con el id 0 se
# dispararía solo cada vez que alguien se arrepiente.
FIRST_ID = 1


def _escape(text: str) -> str:
    """En un menú, `&` marca la letra de atajo y desaparece de la vista. Los
    textos de aquí llevan cifras y detalles del plan, que en Team/Enterprise
    pueden traer un `&` de verdad."""
    return text.replace("&", "&&")


class Menu:
    """Un menú emergente. Se usa una vez y se destruye."""

    def __init__(self) -> None:
        self.hmenu = w.CreatePopupMenu()
        if not self.hmenu:
            raise OSError("CreatePopupMenu falló")
        self._subs: list[Menu] = []

    # ── Construcción ─────────────────────────────────────────
    def item(self, ident: int, text: str, checked: bool = False,
             enabled: bool = True) -> "Menu":
        flags = w.MF_STRING
        if checked:
            flags |= w.MF_CHECKED
        if not enabled:
            flags |= w.MF_GRAYED | w.MF_DISABLED
        w.AppendMenuW(self.hmenu, flags, ident, _escape(text))
        return self

    def label(self, text: str) -> "Menu":
        """Una fila informativa: se ve, no se puede elegir. Es como enseña sus
        cifras el menú de Linux."""
        w.AppendMenuW(self.hmenu, w.MF_STRING | w.MF_GRAYED | w.MF_DISABLED,
                      0, _escape(text))
        return self

    def sep(self) -> "Menu":
        w.AppendMenuW(self.hmenu, w.MF_SEPARATOR, 0, None)
        return self

    def submenu(self, text: str, sub: "Menu") -> "Menu":
        # El HMENU del submenú viaja en el hueco del identificador; `DestroyMenu`
        # del padre se lleva por delante los submenús enganchados.
        w.AppendMenuW(self.hmenu, w.MF_POPUP | w.MF_STRING,
                      int(sub.hmenu), _escape(text))
        self._subs.append(sub)
        return self

    def radio(self, first: int, last: int, checked: int) -> "Menu":
        """Puntos de opción de verdad, no marcas de verificación."""
        w.CheckMenuRadioItem(self.hmenu, first, last, checked, w.MF_BYCOMMAND)
        return self

    # ── Uso ──────────────────────────────────────────────────
    def track(self, hwnd: int, x: int, y: int) -> int:
        """Enseña el menú y devuelve el identificador elegido (0 = cancelado)."""
        w.SetForegroundWindow(hwnd)
        got = w.TrackPopupMenu(
            self.hmenu,
            w.TPM_RIGHTBUTTON | w.TPM_RETURNCMD | w.TPM_NONOTIFY,
            x, y, 0, hwnd, None)
        # Sin este mensaje de relleno el menú no se entera de que perdió el foco
        # y se queda pintado en la pantalla.
        w.PostMessageW(hwnd, w.WM_NULL, 0, 0)
        return int(got)

    def destroy(self) -> None:
        if self.hmenu:
            w.DestroyMenu(self.hmenu)
            self.hmenu = 0
            self._subs.clear()
