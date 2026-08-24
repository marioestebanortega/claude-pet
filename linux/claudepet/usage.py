"""
Lectura del consumo de Claude Code. Sin dependencias: solo la librería estándar.

Es el mismo diseño que la app de macOS, y a propósito no sabe nada de interfaz:
así se puede probar en cualquier sitio, incluido un Mac.
"""
from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass, field

CLAUDE_JSON = os.environ.get("CLAUDEPET_JSON") or os.path.expanduser("~/.claude.json")
STATUSLINE_JSON = os.environ.get("CLAUDEPET_STATUSLINE_JSON") or os.path.expanduser(
    "~/.claude/pet-usage.json"
)

STALE_AFTER = 15 * 60      # segundos
ACTIVE_WITHIN = 3 * 60     # Claude Code se considera vivo si tocó un archivo hace poco


# ─────────────────────────────────────────────────────────────
# Modelo
# ─────────────────────────────────────────────────────────────

@dataclass
class Limit:
    id: str
    label: str
    percent: int
    resets_at: float | None = None   # epoch en segundos
    is_active: bool = False
    group: str = ""
    detail: str | None = None        # "US$ 310 de US$ 500" en planes por dinero


@dataclass
class Usage:
    limits: list[Limit] = field(default_factory=list)
    fetched_at: float = 0.0
    source: str = ""

    def by_id(self, wanted: str) -> Limit | None:
        return next((l for l in self.limits if l.id == wanted), None)

    @property
    def session(self) -> Limit | None:
        return self.by_id("session")

    @property
    def weekly(self) -> Limit | None:
        return self.by_id("weekly_all")

    @property
    def _extra(self) -> list[Limit]:
        """Todo lo demás que traiga el plan, incluido lo que aún no existe.
        Se ocultan las que están a cero y sin cifra, que solo serían ruido."""
        return [
            l for l in self.limits
            if l.id not in ("session", "weekly_all")
            and (l.percent > 0 or l.detail or l.is_active)
        ]

    @property
    def _fallback_top(self) -> list[Limit]:
        """Team/Enterprise no traen "session"/"weekly_all": ahí se cae a las dos
        dimensiones con más porcentaje de lo que sí trajo el plan (gasto, créditos…)
        en vez de mostrar 0/0% con la cuota real en 2%."""
        return sorted(self._extra, key=lambda l: l.percent, reverse=True)

    @property
    def others(self) -> list[Limit]:
        """Lista larga del panel: todo lo extra, salvo lo que ya se repite arriba
        como sesión/semana de repuesto."""
        if self.session or self.weekly:
            return self._extra
        shown = {l.id for l in self._fallback_top[:2]}
        return [l for l in self._extra if l.id not in shown]

    @property
    def session_pct(self) -> int:
        if self.session:
            return self.session.percent
        top = self._fallback_top
        return top[0].percent if top else 0

    @property
    def week_pct(self) -> int:
        if self.weekly:
            return self.weekly.percent
        top = self._fallback_top
        return top[1].percent if len(top) > 1 else 0

    @property
    def has_free_source(self) -> bool:
        """Si el plan publica `rate_limits` (Pro/Max) hay una fuente que se
        refresca sola y gratis... mientras Claude Code esté abierto, porque la
        escribe el hook de `statusLine`. Team/Enterprise no la tiene nunca."""
        return self.session is not None or self.weekly is not None

    @property
    def has_secondary(self) -> bool:
        """true si hay una segunda ventana real que mostrar. Con una sola
        dimensión, la UI compacta enseña un número en vez de inventar una
        "semana" en 0% que no existe."""
        return self.weekly is not None or len(self._fallback_top) > 1

    @property
    def compact_text(self) -> str:
        """Badge/etiqueta: "sesión/semana" cuando hay dos ventanas reales,
        un solo número cuando el plan solo separa una (Team/Enterprise)."""
        if self.has_secondary:
            return f"{self.session_pct}/{self.week_pct}%"
        return f"{self.session_pct}%"

    @property
    def worst(self) -> int:
        return max((l.percent for l in self.limits), default=0)

    @property
    def age(self) -> float:
        return time.time() - self.fetched_at

    @property
    def is_stale(self) -> bool:
        return self.age > STALE_AFTER


# ─────────────────────────────────────────────────────────────
# Humor
# ─────────────────────────────────────────────────────────────

MOODS = ["chill", "ok", "alert", "panic", "broken"]

# Mismos colores que la versión de macOS: relleno, fondo sólido, texto.
MOOD_COLORS = {
    "chill":  (0x34C759, 0x1E9455),
    "ok":     (0xFFB020, 0xB07A06),
    "alert":  (0xFF8A2B, 0xC4551C),
    "panic":  (0xFF4D4D, 0xC42B2B),
    "broken": (0x98989D, 0x6E6E73),
}


def mood_for(pct: int) -> str:
    if pct < 40:
        return "chill"
    if pct < 70:
        return "ok"
    if pct < 90:
        return "alert"
    return "panic"


# ─────────────────────────────────────────────────────────────
# Utilidades
# ─────────────────────────────────────────────────────────────

def _load(path: str) -> dict | None:
    try:
        with open(path, "rb") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _iso(value) -> float | None:
    """`resets_at` llega como ISO-8601 o como epoch en segundos."""
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    text = value.replace("Z", "+00:00")
    try:
        from datetime import datetime
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return None


def _money(value: float, currency: str | None) -> str:
    """Formato español fijo: punto para miles, coma para decimales.

    A propósito NO depende del locale del sistema (la app de macOS usa
    NumberFormatter, que sí; en un equipo en inglés daría "$1,234.56"). Aquí
    siempre sale en estilo español para dar una presentación estable.
    """
    symbol = {"USD": "US$", "EUR": "€", "GBP": "£"}.get(currency or "USD", (currency or "") + " ")
    digits = 0 if abs(value) >= 100 else 2
    text = f"{value:,.{digits}f}"
    # De 1,234.56 a 1.234,56
    text = text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return f"{symbol} {text}"


def _minor(d) -> float | None:
    """`amount_minor` viene en la unidad menor, con su propio exponente."""
    if not isinstance(d, dict) or not isinstance(d.get("amount_minor"), (int, float)):
        return None
    return d["amount_minor"] / math.pow(10, d.get("exponent", 2))


def _label(kind: str, scope: dict | None) -> str:
    known = {
        "session": "Sesión (5 h)",
        "weekly_all": "Semana (todos los modelos)",
        "monthly": "Mes",
        "daily": "Día",
        "spend": "Gasto",
    }
    if kind in known:
        return known[kind]
    if kind == "weekly_scoped":
        scope = scope or {}
        name = (scope.get("model") or {}).get("display_name") \
            or (scope.get("surface") or {}).get("display_name")
        return f"Semana ({name or 'acotado'})"
    # Un plan puede traer dimensiones nuevas: mejor legibles que descartadas.
    return kind.replace("_", " ").title()


# ─────────────────────────────────────────────────────────────
# Fuentes
# ─────────────────────────────────────────────────────────────

def _kind_key(kind: str) -> str:
    return {"session": "five_hour", "weekly_all": "seven_day"}.get(kind, kind)


def _dollar_detail(window) -> str | None:
    if not isinstance(window, dict):
        return None
    used, limit = window.get("used_dollars"), window.get("limit_dollars")
    if not isinstance(used, (int, float)) or not isinstance(limit, (int, float)) or limit <= 0:
        return None
    return f"{_money(used, 'USD')} de {_money(limit, 'USD')}"


def _spend_limits(util: dict) -> list[Limit]:
    """Gasto en dinero (`spend`) y créditos mensuales (`extra_usage`): la métrica
    de Team y Enterprise. En Pro/Max vienen vacíos y no se dibuja nada."""
    spend = util.get("spend")
    sp_used = sp_cap = None
    spend_entry: Limit | None = None
    if isinstance(spend, dict):
        sp_used = _minor(spend.get("used"))
        sp_cap = _minor(spend.get("limit")) or _minor(spend.get("cap"))
        sp_pct = int(spend.get("percent") or 0)
        currency = (spend.get("used") or {}).get("currency")
        if sp_cap is not None or sp_pct > 0 or (sp_used or 0) > 0:
            detail = None
            if sp_used is not None and sp_cap is not None:
                detail = f"{_money(sp_used, currency)} de {_money(sp_cap, currency)}"
            elif sp_used:
                detail = _money(sp_used, currency)
            spend_entry = Limit("spend", "Gasto", sp_pct, None,
                                bool(spend.get("enabled")), "spend", detail)

    out: list[Limit] = []
    extra = util.get("extra_usage")
    if isinstance(extra, dict) and extra.get("is_enabled"):
        # "decimal_places", no "exponent": mismos centavos que `spend`, otra clave.
        dp = extra.get("decimal_places")
        scale = 10 ** (dp if isinstance(dp, (int, float)) else 2)
        cur = extra.get("currency")
        raw_used, raw_cap = extra.get("used_credits"), extra.get("monthly_limit")
        used = raw_used / scale if isinstance(raw_used, (int, float)) else None
        cap = raw_cap / scale if isinstance(raw_cap, (int, float)) else None
        detail = None
        if used is not None and cap is not None:
            detail = f"{_money(used, cur)} de {_money(cap, cur)}"
        credits_entry = Limit("extra_usage", "Créditos del mes",
                              round(extra.get("utilization") or 0), None,
                              not extra.get("spend_limit_reached"), "monthly", detail)

        # `spend` y los créditos suelen ser la misma bolsa vista dos veces (mismo
        # usado, mismo tope). Mostrar las dos por separado es el "2/2%" confuso,
        # como si fueran dos ventanas distintas — si coinciden, una basta.
        same_bolsa = (sp_used is not None and used is not None
                      and abs(sp_used - used) < 0.01
                      and abs((sp_cap if sp_cap is not None else -1)
                              - (cap if cap is not None else -2)) < 0.01)
        out.append(credits_entry)
        if spend_entry and not same_bolsa:
            out.append(spend_entry)

        # El límite mensual puede llevar sub-ventanas diaria y semanal.
        for key, name in (("daily", "Créditos del día"), ("weekly", "Créditos de la semana")):
            sub = extra.get(key)
            if not isinstance(sub, dict):
                continue
            raw_u = sub.get("used_credits")
            raw_c = sub.get("limit")
            if not isinstance(raw_c, (int, float)):
                raw_c = sub.get("monthly_limit")
            u = raw_u / scale if isinstance(raw_u, (int, float)) else None
            c = raw_c / scale if isinstance(raw_c, (int, float)) else None
            d = None
            if u is not None and c is not None:
                d = f"{_money(u, cur)} de {_money(c, cur)}"
            out.append(Limit(f"extra_{key}", name, round(sub.get("utilization") or 0),
                             _iso(sub.get("resets_at")), False, key, d))
    elif spend_entry:
        out.append(spend_entry)
    return out


def _drop_expired(limits: list[Limit]) -> list[Limit]:
    """Quita ventanas ya vencidas.

    Si `resets_at` quedó atrás, esa cifra es de un ciclo anterior. Pasa porque
    todas las sesiones de Claude Code escriben el mismo `pet-usage.json`: una
    que lleva horas quieta reescribe su foto vieja con marca de tiempo nueva.
    Un minuto de margen para el desfase de relojes.
    """
    now = time.time()
    return [l for l in limits if not l.resets_at or l.resets_at > now - 60]


def from_claude_json() -> Usage | None:
    """Fuente rica: todas las dimensiones, pero se refresca poco."""
    root = _load(CLAUDE_JSON)
    cached = (root or {}).get("cachedUsageUtilization")
    util = (cached or {}).get("utilization")
    if not isinstance(util, dict):
        return None

    ms = cached.get("fetchedAtMs")
    u = Usage(source="~/.claude.json",
              # Si falta la marca, "ahora": un 0 daría age gigante → siempre stale
              # y estropearía la fusión en best(). Igual que la app de macOS.
              fetched_at=ms / 1000 if isinstance(ms, (int, float)) else time.time())

    for entry in util.get("limits") or []:
        kind = entry.get("kind", "?")
        scope = entry.get("scope")
        lid = kind
        if kind == "weekly_scoped":
            model = ((scope or {}).get("model") or {}).get("display_name", "?")
            lid = f"weekly_scoped:{model}"
        u.limits.append(Limit(
            id=lid,
            label=_label(kind, scope),
            percent=round(entry.get("percent") or 0),
            resets_at=_iso(entry.get("resets_at")),
            is_active=bool(entry.get("is_active")),
            group=entry.get("group") or kind,
            detail=_dollar_detail(util.get(_kind_key(kind))),
        ))

    if not u.limits:
        # Respaldo por si algún día desaparece `limits`.
        for key, lid, label, grp in (
            ("five_hour", "session", "Sesión (5 h)", "session"),
            ("seven_day", "weekly_all", "Semana (todos los modelos)", "weekly"),
        ):
            w = util.get(key)
            if isinstance(w, dict) and isinstance(w.get("utilization"), (int, float)):
                u.limits.append(Limit(lid, label, round(w["utilization"]),
                                      _iso(w.get("resets_at")), True, grp,
                                      _dollar_detail(w)))

    u.limits.extend(_spend_limits(util))
    u.limits = _drop_expired(u.limits)
    return u if u.limits else None


def from_statusline() -> Usage | None:
    """Fuente fresca: se reescribe cada pocos segundos, pero solo trae dos ventanas."""
    root = _load(STATUSLINE_JSON)
    rl = (root or {}).get("rate_limits")
    if not isinstance(rl, dict):
        return None

    stamp = root.get("written_at_ms")
    fetched = (stamp / 1000 if isinstance(stamp, (int, float))
               else _mtime(STATUSLINE_JSON) or time.time())
    u = Usage(source="statusLine", fetched_at=fetched)

    for key, lid, label, grp in (
        ("five_hour", "session", "Sesión (5 h)", "session"),
        ("seven_day", "weekly_all", "Semana (todos los modelos)", "weekly"),
    ):
        w = rl.get(key)
        if not isinstance(w, dict) or not isinstance(w.get("used_percentage"), (int, float)):
            continue
        u.limits.append(Limit(lid, label, round(w["used_percentage"]),
                              _iso(w.get("resets_at")), True, grp))
    u.limits = _drop_expired(u.limits)
    return u if u.limits else None


def _mtime(path: str) -> float | None:
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def best() -> Usage | None:
    """
    No se elige una fuente, se fusionan.

    `statusLine` es más fresco pero solo trae sesión y semana; `~/.claude.json`
    trae además el gasto y los créditos, que es lo que miden los planes de
    empresa. Quedarse con "la más reciente" perdería esas dimensiones.
    """
    rich, fresh = from_claude_json(), from_statusline()
    if rich is None:
        return fresh
    if fresh is None or fresh.fetched_at <= rich.fetched_at:
        return rich

    merged = Usage(list(rich.limits), fresh.fetched_at, "statusLine + ~/.claude.json")
    for f in fresh.limits:
        for i, old in enumerate(merged.limits):
            if old.id == f.id:
                merged.limits[i] = Limit(old.id, old.label, f.percent,
                                         f.resets_at or old.resets_at,
                                         old.is_active, old.group, old.detail)
                break
        else:
            merged.limits.append(f)
    return merged


def statusline_changed_at() -> float | None:
    """Cuándo se movieron por última vez los porcentajes del hook.

    No es lo mismo que `written_at_ms`: el hook reescribe el archivo cada ~10 s
    con marca nueva aunque las cifras no hayan cambiado, porque Claude Code las
    refresca a saltos. Por eso `fetched_at` nunca envejece mientras haya una
    sesión viva, y sin esta segunda señal no se distingue "recién escrito" de
    "recién actualizado".

    Devuelve None si el hook es de una versión anterior a `changed_at_ms`: ahí
    no se sabe, y no saber no debe disparar nada.
    """
    root = _load(STATUSLINE_JSON)
    ms = (root or {}).get("changed_at_ms")
    return ms / 1000 if isinstance(ms, (int, float)) else None


def figures_look_frozen() -> bool:
    """Las cifras llevan clavadas más de lo que dura una ventana de frescura,
    aunque el archivo se siga reescribiendo.

    Puede ser que Claude Code no las haya refrescado... o que simplemente no
    estés consumiendo nada: desde el archivo no se distingue. Por eso esto solo
    sirve para ir a preguntar con `/usage` —que es barato y resuelve la duda— y
    nunca para pintar el dato como viejo, que daría un falso positivo cada vez
    que te levantas a comer.
    """
    changed = statusline_changed_at()
    return changed is not None and time.time() - changed > STALE_AFTER


def claude_code_active(within: float = ACTIVE_WITHIN) -> bool:
    """Claude Code reescribe estos archivos mientras corre. Es un stat, nada más."""
    now = time.time()
    return any((m := _mtime(p)) and now - m < within
               for p in (STATUSLINE_JSON, CLAUDE_JSON))


def empty_reason() -> str:
    """Distinguir "aún no" de "nunca": con API key no van a aparecer jamás."""
    root = _load(CLAUDE_JSON)
    if root is None:
        return f"No encuentro {CLAUDE_JSON}. ¿Has usado Claude Code en esta máquina?"
    if "oauthAccount" not in root:
        return ("Tu sesión no usa una suscripción de Claude.ai — parece API key, "
                "Bedrock o Vertex. Esos planes se facturan por uso y no publican "
                "ventanas de límite, así que no hay nada que vigilar.")
    if "cachedUsageUtilization" not in root:
        return "Aún no hay cifras de cuota. Usa Claude Code un momento y aparecen."
    return "Tu plan no expone ninguna ventana de límite."
