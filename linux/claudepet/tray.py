"""
Applet de bandeja para GNOME/Ubuntu.

Es la única parte que depende del escritorio. Todo lo demás (leer el consumo,
dibujar a Clawd) vive en módulos sin dependencias, para que `--dump` funcione
aunque GTK no esté instalado.
"""
from __future__ import annotations

import os
import tempfile

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

# Ubuntu moderno trae la variante Ayatana; el nombre viejo sigue en otras distros.
Indicator = None
for name, version in (("AyatanaAppIndicator3", "0.1"), ("AppIndicator3", "0.1")):
    try:
        gi.require_version(name, version)
        Indicator = getattr(__import__("gi.repository", fromlist=[name]), name)
        break
    except (ValueError, ImportError, AttributeError):
        continue

from . import sprite, usage  # noqa: E402

APP_ID = "claudepet"


class Tray:
    def __init__(self, hub, pet=None, on_quit=None) -> None:
        if Indicator is None:
            raise RuntimeError(
                "Falta el soporte de indicadores de bandeja.\n"
                "  sudo apt install gir1.2-ayatanaappindicator3-0.1"
            )
        self.hub = hub
        self.pet = pet
        self.on_quit = on_quit
        self._dir = tempfile.mkdtemp(prefix="claudepet-")
        self._icon_key: tuple | None = None
        self.data: usage.Usage | None = None

        self.menu = Gtk.Menu()
        self.items: list[Gtk.MenuItem] = []
        self._build_menu()

        self.ind = Indicator.Indicator.new(
            APP_ID, self._icon_path(), Indicator.IndicatorCategory.APPLICATION_STATUS
        )
        self.ind.set_status(Indicator.IndicatorStatus.ACTIVE)
        self.ind.set_menu(self.menu)

        hub.subscribe(self._on_data)

    # ── Icono ────────────────────────────────────────────────
    def _icon_path(self, color: int = sprite.BRAND, night: bool = False) -> str:
        key = (color, night)
        path = os.path.join(self._dir, f"clawd-{color:06x}-{int(night)}.png")
        if self._icon_key != key or not os.path.exists(path):
            with open(path, "wb") as f:
                f.write(sprite.render(color=color, night=night, cell=4))
            self._icon_key = key
        return path

    # ── Menú ─────────────────────────────────────────────────
    def _build_menu(self) -> None:
        for _ in range(10):                       # filas reutilizables
            item = Gtk.MenuItem(label="")
            item.set_sensitive(False)
            item.hide()
            self.menu.append(item)
            self.items.append(item)

        self.menu.append(Gtk.SeparatorMenuItem())

        self.freshness = Gtk.MenuItem(label="")
        self.freshness.set_sensitive(False)
        self.menu.append(self.freshness)

        if self.pet is not None:
            self.pet_item = Gtk.CheckMenuItem(label="Mascota en el escritorio")
            self.pet_item.set_active(self.pet.get_visible())
            self.pet_item.connect("toggled", self._toggle_pet)
            self.menu.append(self.pet_item)

        refresh = Gtk.MenuItem(label="Actualizar ahora")
        refresh.connect("activate", lambda *_: self.hub.refresh(force=True))
        self.menu.append(refresh)

        # "Forzar": pregunta al servidor con `claude -p "/usage"`, que reescribe el
        # caché con cifras frescas. Útil en Team/Enterprise, donde ~/.claude.json
        # se refresca poco. `/usage` es una consulta de estado: coste ~nulo.
        self._force_item = Gtk.MenuItem(label="Forzar (/usage)")
        self._force_item.connect("activate", lambda *_: self.hub.force_usage(self._on_force_state))
        self.menu.append(self._force_item)

        self.menu.append(Gtk.SeparatorMenuItem())

        quit_item = Gtk.MenuItem(label="Salir de Claude Pet")
        quit_item.connect("activate", lambda *_: (self.on_quit or Gtk.main_quit)())
        self.menu.append(quit_item)

        self.menu.show_all()
        for item in self.items:
            item.hide()

    # ── Refresco ─────────────────────────────────────────────
    def _on_data(self, data, changed: bool) -> None:
        self.data = data
        if changed:
            self._render()
        else:
            self._render_freshness()               # solo envejece el texto

    def _render(self) -> None:
        data = self.data
        if data is None:
            self.ind.set_label("—", "100/100%")
            self._show_rows([usage.empty_reason()])
            self.ind.set_icon_full(
                self._icon_path(usage.MOOD_COLORS["broken"][0]), "Claude Pet"
            )
            self._render_freshness()
            return

        night = _is_night()
        mood = usage.mood_for(data.worst)
        # Clawd conserva su naranja de marca; el humor va en el texto.
        self.ind.set_icon_full(self._icon_path(sprite.BRAND, night), "Claude Pet")
        self.ind.set_label(data.compact_text, "100/100%")

        rows = []
        for limit in [l for l in (data.session, data.weekly) if l] + data.others:
            line = f"{limit.label}   {limit.percent}%"
            if limit.detail:
                line += f"   ({limit.detail})"
            rows.append(line)
        rows.append(f"— humor: {mood}" + ("  ·  🌙 modo noche" if night else ""))
        self._show_rows(rows)
        self._render_freshness()

    def _render_freshness(self) -> None:
        if self.data is None:
            self.freshness.set_label("sin datos")
            return
        stale = self.data.is_stale and usage.claude_code_active()
        mark = "⚠︎ " if stale else ""
        self.freshness.set_label(
            f"{mark}dato de hace {_ago(self.data.age)} · {self.data.source}"
        )

    def _on_force_state(self, running: bool, error: str | None) -> None:
        """Feedback del botón "Forzar" (siempre llega en el bucle principal)."""
        self._force_item.set_label("Consultando…" if running else "Forzar (/usage)")
        self._force_item.set_sensitive(not running)
        # Al acabar, hub ya releyó (→ _render); si hubo error se muestra aquí, que
        # es lo último, y el siguiente sondeo (5 s) lo revierte al texto normal.
        if error and not running:
            self.freshness.set_label(f"⚠︎ {error}")

    def _toggle_pet(self, item) -> None:
        if item.get_active():
            self.pet.show_pet()
        else:
            self.pet.hide_pet()

    def sync_pet_item(self) -> None:
        """La mascota también se esconde desde su propio menú."""
        if self.pet is None:
            return
        want = self.pet.get_visible()
        if self.pet_item.get_active() != want:
            self.pet_item.handler_block_by_func(self._toggle_pet)
            self.pet_item.set_active(want)
            self.pet_item.handler_unblock_by_func(self._toggle_pet)

    def _show_rows(self, rows: list[str]) -> None:
        # Hay 10 filas reutilizables; si el plan trae más dimensiones, no se
        # descartan en silencio: la última se convierte en "…y N más".
        n = len(self.items)
        if len(rows) > n:
            hidden = len(rows) - (n - 1)
            rows = rows[:n - 1] + [f"…y {hidden} más"]
        for item, text in zip(self.items, rows):
            item.set_label(text)
            item.show()
        for item in self.items[len(rows):]:
            item.hide()


def _ago(seconds: float) -> str:
    seconds = int(max(0, seconds))
    if seconds < 60:
        return f"{seconds} s"
    if seconds < 3600:
        return f"{seconds // 60} min"
    if seconds < 86400:
        return f"{seconds // 3600} h"
    return f"{seconds // 86400} d"


def _is_night() -> bool:
    import datetime
    hour = datetime.datetime.now().hour
    return hour >= 18 or hour < 6
