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
from gi.repository import GLib, Gtk  # noqa: E402

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

POLL_SECONDS = 5
APP_ID = "claudepet"


class Tray:
    def __init__(self) -> None:
        if Indicator is None:
            raise RuntimeError(
                "Falta el soporte de indicadores de bandeja.\n"
                "  sudo apt install gir1.2-ayatanaappindicator3-0.1"
            )
        self._dir = tempfile.mkdtemp(prefix="claudepet-")
        self._icon_key: tuple | None = None
        self._stamps: tuple | None = None
        self.data: usage.Usage | None = None

        self.menu = Gtk.Menu()
        self.items: list[Gtk.MenuItem] = []
        self._build_menu()

        self.ind = Indicator.Indicator.new(
            APP_ID, self._icon_path(), Indicator.IndicatorCategory.APPLICATION_STATUS
        )
        self.ind.set_status(Indicator.IndicatorStatus.ACTIVE)
        self.ind.set_menu(self.menu)

        self.refresh(force=True)
        GLib.timeout_add_seconds(POLL_SECONDS, self._tick)

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

        refresh = Gtk.MenuItem(label="Actualizar ahora")
        refresh.connect("activate", lambda *_: self.refresh(force=True))
        self.menu.append(refresh)

        self.menu.append(Gtk.SeparatorMenuItem())

        quit_item = Gtk.MenuItem(label="Salir de Claude Pet")
        quit_item.connect("activate", lambda *_: Gtk.main_quit())
        self.menu.append(quit_item)

        self.menu.show_all()
        for item in self.items:
            item.hide()

    # ── Refresco ─────────────────────────────────────────────
    def _tick(self) -> bool:
        self.refresh()
        return True                                # seguir llamando

    def refresh(self, force: bool = False) -> None:
        stamps = tuple(
            os.path.getmtime(p) if os.path.exists(p) else None
            for p in (usage.CLAUDE_JSON, usage.STATUSLINE_JSON)
        )
        if not force and stamps == self._stamps and self.data is not None:
            self._render_freshness()               # solo envejece el texto
            return
        self._stamps = stamps
        self.data = usage.best()
        self._render()

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
        self.ind.set_label(f"{data.session_pct}/{data.week_pct}%", "100/100%")

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

    def _show_rows(self, rows: list[str]) -> None:
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


def main() -> int:
    Tray()
    Gtk.main()
    return 0
