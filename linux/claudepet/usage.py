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
    def others(self) -> list[Limit]:
        """Todo lo demás que traiga el plan, incluido lo que aún no existe."""
        return [
            l for l in self.limits
            if l.id not in ("session", "weekly_all")
            and (l.percent > 0 or l.detail or l.is_active)
        ]

    @property
    def session_pct(self) -> int:
        return self.session.percent if self.session else 0

    @property
    def week_pct(self) -> int:
        return self.weekly.percent if self.weekly else 0

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
    """Formato español: punto para miles, coma para decimales, como en macOS."""
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
    """Gasto en dinero y créditos mensuales: la métrica de Team y Enterprise."""
    out: list[Limit] = []

    spend = util.get("spend")
    if isinstance(spend, dict):
        used = _minor(spend.get("used"))
        cap = _minor(spend.get("limit")) or _minor(spend.get("cap"))
        pct = int(spend.get("percent") or 0)
        currency = (spend.get("used") or {}).get("currency")
        if cap is not None or pct > 0 or (used or 0) > 0:
            detail = None
            if used is not None and cap is not None:
                detail = f"{_money(used, currency)} de {_money(cap, currency)}"
            elif used:
                detail = _money(used, currency)
            out.append(Limit("spend", "Gasto", pct, None,
                             bool(spend.get("enabled")), "spend", detail))

    extra = util.get("extra_usage")
    if isinstance(extra, dict) and extra.get("is_enabled"):
        cur = extra.get("currency")
        used, cap = extra.get("used_credits"), extra.get("monthly_limit")
        detail = None
        if isinstance(used, (int, float)) and isinstance(cap, (int, float)):
            detail = f"{_money(used, cur)} de {_money(cap, cur)}"
        out.append(Limit("extra_usage", "Créditos del mes",
                         int(extra.get("utilization") or 0), None,
                         not extra.get("spend_limit_reached"), "monthly", detail))

        for key, name in (("daily", "Créditos del día"), ("weekly", "Créditos de la semana")):
            sub = extra.get(key)
            if not isinstance(sub, dict):
                continue
            u, c = sub.get("used_credits"), sub.get("limit") or sub.get("monthly_limit")
            d = None
            if isinstance(u, (int, float)) and isinstance(c, (int, float)):
                d = f"{_money(u, cur)} de {_money(c, cur)}"
            out.append(Limit(f"extra_{key}", name, int(sub.get("utilization") or 0),
                             _iso(sub.get("resets_at")), False, key, d))
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

    u = Usage(source="~/.claude.json",
              fetched_at=(cached.get("fetchedAtMs") or 0) / 1000)

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
            percent=int(entry.get("percent") or 0),
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
                u.limits.append(Limit(lid, label, int(w["utilization"]),
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
    fetched = stamp / 1000 if stamp else _mtime(STATUSLINE_JSON) or 0
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
