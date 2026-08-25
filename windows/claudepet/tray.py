"""
El icono de la bandeja y su menú.

Es, con la mascota, la única parte que depende del escritorio. Todo lo demás
—leer el consumo, dibujar a Clawd— vive en módulos sin dependencias, para que
`--dump` funcione aunque algo de la interfaz esté roto.

Dos diferencias de fondo con el applet de Linux, que se notan en todo el archivo:

- **No hay etiqueta de texto.** `AppIndicator.set_label("😺 25%")` no tiene
  equivalente: la bandeja de Windows enseña un icono y un tooltip, y nada más.
  La cifra se pinta dentro del icono (ver `icon.py`) y la línea completa va al
  tooltip.
- **El menú se construye cada vez que se abre**, porque `TrackPopupMenu` no es
  persistente (ver `menu.py`). Eso quita de en medio las diez filas
  reutilizables y toda la sincronización de casillas del applet de GTK.
"""
from __future__ import annotations

import ctypes
import datetime

from . import icon, loop, menu, notify, sprite, usage
from . import win32 as w
from .hub import AUTO_FORCE_CPU_SECONDS, AUTO_FORCE_OPTIONS

ICON_UID = 1

# Cómo se lee cada intervalo del selector.
AUTO_FORCE_LABELS = {60: "cada minuto", 120: "cada 2 min", 300: "cada 5 min"}

# Identificadores del menú. Empiezan en 1 (ver `menu.FIRST_ID`).
ID_PET = 1
ID_REFRESH = 2
ID_FORCE = 3
ID_AUTO = 4
ID_NOTIFY = 5
ID_QUIT = 6
ID_INTERVAL = 10                       # 10, 11, 12 — uno por opción


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
    hour = datetime.datetime.now().hour
    return hour >= 18 or hour < 6


class Tray:
    def __init__(self, hub, window, pet=None, on_quit=None) -> None:
        """`window` es la ventana oculta que crea `app.py` y de la que ya cuelga
        el temporizador. No la crea la bandeja porque el `Hub` la necesita antes
        —el `Scheduler` se apoya en ella— y porque con `--no-pet` o sin bandeja
        el proceso sigue necesitando una."""
        self.hub = hub
        self.pet = pet
        self.on_quit = on_quit
        self.data: usage.Usage | None = None
        self._hicon = 0
        self._icon_key: tuple | None = None
        self._forcing = False
        self._error: str | None = None
        self._added = False
        self._retries = 0

        self.window = window
        self.hwnd = window.hwnd
        self.sched = hub.sched
        notify.bind(self, self.sched)

        self.nid = w.NOTIFYICONDATAW()
        self.nid.cbSize = ctypes.sizeof(w.NOTIFYICONDATAW)
        self.nid.hWnd = self.hwnd
        self.nid.uID = ICON_UID
        self.nid.uCallbackMessage = loop.WM_APP_TRAY

        self._add_icon()
        hub.subscribe(self._on_data)

    # ── El icono ─────────────────────────────────────────────
    def _icon_size(self) -> int:
        return w.small_icon_size(self.hwnd)

    def _make_icon(self, color: int, night: bool, percent: int | None,
                   accent: int | None = None) -> None:
        """Rehace el HICON solo si cambió algo. Recrearlo en cada sondeo serían
        miles de objetos GDI al día y el proceso moriría al llegar a la cuota."""
        size = self._icon_size()
        key = (size, color, night, percent, accent)
        if key == self._icon_key and self._hicon:
            return
        new = icon.hicon(size, color=color, night=night, percent=percent,
                         accent=accent)
        if not new:
            return
        old = self._hicon
        self._hicon, self._icon_key = new, key
        self.nid.hIcon = new
        self._modify(w.NIF_ICON)
        if old:
            w.DestroyIcon(old)             # el viejo, y solo después de cambiarlo

    def _add_icon(self) -> bool:
        """Pone el icono. Al iniciar sesión puede fallar porque la barra de
        tareas todavía no existe, así que se reintenta unas cuantas veces."""
        self.nid.uFlags = w.NIF_MESSAGE | w.NIF_TIP | w.NIF_SHOWTIP
        if self._hicon:
            self.nid.uFlags |= w.NIF_ICON
        if not w.Shell_NotifyIconW(w.NIM_ADD, ctypes.byref(self.nid)):
            self._retries += 1
            if self._retries <= 5:
                self.sched.after(2000, lambda: (self._add_icon(), False)[1])
            return False
        self._added = True
        self._retries = 0
        # Versión 4: el punto de anclaje del menú llega ya en coordenadas de
        # pantalla correctas para el DPI, sin tener que pedir la posición del
        # cursor por otro lado y arriesgarse a una carrera.
        self.nid.uVersion = w.NOTIFYICON_VERSION_4
        w.Shell_NotifyIconW(w.NIM_SETVERSION, ctypes.byref(self.nid))
        self._render()
        return True

    def _modify(self, flags: int) -> bool:
        if not self._added:
            return False
        self.nid.uFlags = flags
        return bool(w.Shell_NotifyIconW(w.NIM_MODIFY, ctypes.byref(self.nid)))

    def _set_tip(self, text: str) -> None:
        self.nid.szTip = text[:127]        # ctypes no recorta: lanzaría ValueError
        self._modify(w.NIF_TIP | w.NIF_SHOWTIP)

    def balloon(self, title: str, body: str, warning: bool = False) -> bool:
        """El globo de aviso. Devuelve False si el shell no lo aceptó; que lo
        acepte no garantiza que se vea (ver `notify.py`)."""
        self.nid.szInfoTitle = title[:63]
        self.nid.szInfo = body[:255]
        self.nid.dwInfoFlags = ((w.NIIF_WARNING if warning else w.NIIF_INFO)
                                | w.NIIF_RESPECT_QUIET_TIME)
        return self._modify(w.NIF_INFO)

    # ── Mensajes ─────────────────────────────────────────────
    def on_message(self, msg: int, wparam: int, lparam: int):
        got = self.sched.handle(msg, wparam, lparam)
        if got is not None:
            return got
        if msg == loop.WM_APP_TRAY:
            return self._on_tray(wparam, lparam)
        if msg == loop.WM_TASKBAR_CREATED:
            # El Explorador se ha reiniciado y se llevó el icono por delante.
            self._added = False
            self._retries = 0
            self._add_icon()
            return 0
        if msg == loop.WM_CLAUDEPET_SHOW:
            # Otra instancia ha intentado arrancar. En Windows 11 el icono suele
            # quedar escondido en el desbordamiento, así que lo que se enseña es
            # la mascota: es la respuesta visible a un doble clic que, si no,
            # parecería no haber hecho nada.
            if self.pet is not None:
                self.pet.show_pet()
                self.pet.recenter()
            return 0
        if msg in (w.WM_ENDSESSION, w.WM_QUERYENDSESSION):
            self.dispose()                 # sin esto queda un icono fantasma
            return None
        if msg == w.WM_DESTROY:
            self.dispose()
            return 0
        return None

    def _on_tray(self, wparam: int, lparam: int) -> int:
        # Con la versión 4, wparam trae las coordenadas de anclaje y lparam el
        # suceso. Extensión de signo obligatoria: un monitor a la izquierda del
        # principal tiene coordenadas negativas.
        x, y = w.get_x(wparam), w.get_y(wparam)
        event = w.loword(lparam)
        if event in (w.WM_CONTEXTMENU, w.NIN_SELECT, w.NIN_KEYSELECT):
            # Clic izquierdo y derecho abren el mismo menú, como el applet de
            # Linux, donde AppIndicator lo enseña con cualquiera de los dos.
            self._popup(x, y)
        elif event == w.NIN_BALLOONSHOW:
            notify.balloon_shown()
        elif event == w.NIN_BALLOONUSERCLICK and self.pet is not None:
            self.pet.show_pet()
            self.pet.recenter()
        return 0

    # ── El menú ──────────────────────────────────────────────
    def _rows(self) -> list[str]:
        data = self.data
        if data is None:
            return [usage.empty_reason()]
        rows = []
        # Pro/Max: session + weekly; Enterprise: los dos más usados como sustituto.
        # `others` ya excluye esos dos para evitar duplicados.
        top = [l for l in (data.session, data.weekly) if l] or data._fallback_top[:2]
        for limit in top + data.others:
            line = f"{limit.label}   {limit.percent}%"
            if limit.detail:
                line += f"   ({limit.detail})"
            rows.append(line)
        night = _is_night()
        rows.append(f"— humor: {usage.mood_for(data.worst)}"
                    + ("  ·  🌙 modo noche" if night else ""))
        return rows

    def _freshness(self) -> str:
        if self._error:
            return f"⚠ {self._error}"
        if self.data is None:
            return "sin datos"
        mark = "⚠ " if self.data.is_stale and usage.claude_code_active() else ""
        return f"{mark}dato de hace {_ago(self.data.age)} · {self.data.source}"

    def _auto_cost(self) -> str:
        """Lo que cuesta de verdad. Se enseña para que la decisión no sea a
        ciegas: en Pro/Max el intervalo del selector no manda, porque dos
        consultas no pueden caer más juntas que `STALE_AFTER`."""
        secs = max(60, self.hub.auto_force_seconds)
        free = self.data is not None and self.data.has_free_source
        real = max(secs, usage.STALE_AFTER) if free else secs
        pct = f"{AUTO_FORCE_CPU_SECONDS / real * 100:.1f}".replace(".", ",")
        return f"~{pct} % de un núcleo"

    def _build_menu(self) -> menu.Menu:
        m = menu.Menu()
        for row in self._rows():
            m.label(row)
        m.sep()
        m.label(self._freshness())
        if self.pet is not None:
            m.item(ID_PET, "Mascota en el escritorio", checked=self.pet.get_visible())
        m.item(ID_REFRESH, "Actualizar ahora")
        m.item(ID_FORCE, "Consultando…" if self._forcing else "Forzar (/usage)",
               enabled=not self._forcing)

        on = self.hub.auto_force_enabled
        m.item(ID_AUTO, "Consultar /usage sola (no gasta tokens)", checked=on)
        if on:
            free = self.data is not None and self.data.has_free_source
            # El selector solo sale donde manda de verdad: en Pro/Max la consulta
            # solo dispara con el dato viejo, así que el intervalo real lo fija
            # `STALE_AFTER` y no esto.
            if not free:
                sub = menu.Menu()
                for index, seconds in enumerate(AUTO_FORCE_OPTIONS):
                    sub.item(ID_INTERVAL + index,
                             AUTO_FORCE_LABELS.get(seconds, f"cada {seconds} s"))
                chosen = ID_INTERVAL + min(
                    range(len(AUTO_FORCE_OPTIONS)),
                    key=lambda i: abs(AUTO_FORCE_OPTIONS[i] - self.hub.auto_force_seconds))
                sub.radio(ID_INTERVAL, ID_INTERVAL + len(AUTO_FORCE_OPTIONS) - 1, chosen)
                m.submenu("Cada cuánto", sub)
                m.label(f"↳ {self._auto_cost()}")
            else:
                m.label("↳ solo con Claude Code cerrado, si el dato pasa de "
                        f"15 min · {self._auto_cost()}")

        m.item(ID_NOTIFY, "Avisarme al cruzar 50/70/90 %",
               checked=self.hub.notify_enabled)
        m.sep()
        m.item(ID_QUIT, "Salir de Claude Pet")
        return m

    def _popup(self, x: int, y: int) -> None:
        m = self._build_menu()
        try:
            self._run(m.track(self.hwnd, x, y))
        finally:
            m.destroy()

    def _run(self, ident: int) -> None:
        if ident == ID_PET and self.pet is not None:
            self.pet.hide_pet() if self.pet.get_visible() else self.pet.show_pet()
        elif ident == ID_REFRESH:
            self._error = None
            self.hub.refresh(force=True)
        elif ident == ID_FORCE:
            self.hub.force_usage(self._on_force_state)
        elif ident == ID_AUTO:
            self.hub.set_auto_force(not self.hub.auto_force_enabled)
        elif ident == ID_NOTIFY:
            self.hub.set_notify(not self.hub.notify_enabled)
        elif ID_INTERVAL <= ident < ID_INTERVAL + len(AUTO_FORCE_OPTIONS):
            self.hub.set_auto_force_seconds(AUTO_FORCE_OPTIONS[ident - ID_INTERVAL])
        elif ident == ID_QUIT:
            (self.on_quit or loop.quit)()

    # ── Refresco ─────────────────────────────────────────────
    def _on_data(self, data, changed: bool) -> None:
        self.data = data
        if changed:
            self._error = None
            self._render()
        else:
            self._set_tip(self._tooltip())     # solo envejece el texto

    def _tooltip(self) -> str:
        data = self.data
        if data is None:
            return "Claude Pet — sin datos"
        top = [l for l in (data.session, data.weekly) if l] or data._fallback_top[:2]
        parts = [f"{limit.label} {limit.percent} %" for limit in top]
        return "Claude Pet\n" + " · ".join(parts or [f"{data.worst} %"]) + \
               f"\n{self._freshness()}"

    def _render(self) -> None:
        data = self.data
        if data is None:
            self._make_icon(usage.MOOD_COLORS["broken"][0], False, None)
        else:
            # Clawd conserva su naranja de marca y el humor va en la cifra. En
            # Linux el humor viaja en la etiqueta de texto de al lado del icono;
            # aquí esa etiqueta no existe, así que el color se mete en los
            # dígitos, que es donde el ojo va a mirar de todas formas.
            self._make_icon(sprite.BRAND, _is_night(), data.session_pct,
                            accent=usage.MOOD_COLORS[usage.mood_for(data.worst)][0])
        self._set_tip(self._tooltip())

    def _on_force_state(self, running: bool, error: str | None) -> None:
        """Feedback del "Forzar" (siempre llega en el hilo del bucle).

        Aquí no se puede cambiar la etiqueta de un menú que ya está pintado: se
        guarda el estado y lo recoge el próximo `_build_menu`. El error se enseña
        en la fila de frescura hasta el siguiente sondeo, como en Linux.
        """
        self._forcing = running
        if not running:
            self._error = error
            self._set_tip(self._tooltip())

    def sync_pet_item(self) -> None:
        """En Linux hay que sincronizar la casilla porque el menú es persistente.
        Aquí el menú se construye al abrirlo, así que ya nace bien: esto existe
        solo para que `app.py` se lea igual en los dos sistemas."""

    def dispose(self) -> None:
        if self._added:
            w.Shell_NotifyIconW(w.NIM_DELETE, ctypes.byref(self.nid))
            self._added = False
        if self._hicon:
            w.DestroyIcon(self._hicon)
            self._hicon = 0
