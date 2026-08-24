#!/usr/bin/env python3
"""
Hook de statusLine para Claude Code.
Guarda el bloque `rate_limits` en ~/.claude/pet-usage.json (para Claude Pet)
e imprime una línea de estado. No consume cuota: corre 100% local.
"""
import fcntl, json, os, sys, time

HOME = os.path.expanduser("~")
OUT = os.path.join(HOME, ".claude", "pet-usage.json")
LOCK = OUT + ".lock"


def merge(new, old):
    """Combina la foto nueva con la guardada, ventana por ventana.

    Existe porque **todas las sesiones de Claude Code escriben este mismo
    archivo**. Una sesión que lleva horas quieta sigue rindiendo su línea de
    estado cada pocos segundos, con sus cifras de entonces y una marca de
    tiempo de ahora: sobrescribir a ciegas hacía que la mascota rebotara entre
    el dato bueno y el viejo cada pocos segundos.

    La regla se apoya en `resets_at`, que identifica la ventana:

    - ventana posterior  → el dato nuevo manda (la anterior ya se reinició)
    - ventana anterior   → la foto entrante es vieja, se ignora
    - misma ventana      → gana el porcentaje mayor: dentro de una ventana el
                           consumo solo puede subir hasta que se reinicia

    Dos sesiones pueden leer y escribir a la vez y pisarse un ciclo; al render
    siguiente se corrige solo, así que no vale la pena un bloqueo.
    """
    if not isinstance(old, dict):
        return new
    out = dict(old)
    for key, w in new.items():
        prev = out.get(key)
        if not isinstance(w, dict):
            continue                  # basura entrante: no pisa lo que ya había
        if not isinstance(prev, dict):
            out[key] = w              # no había nada usable: se guarda tal cual
            continue
        r_new, r_old = w.get("resets_at"), prev.get("resets_at")
        if not isinstance(r_new, (int, float)) or not isinstance(r_old, (int, float)):
            out[key] = w
        elif r_new > r_old:
            out[key] = w
        elif r_new == r_old:
            p_new, p_old = w.get("used_percentage"), prev.get("used_percentage")
            if not isinstance(p_new, (int, float)) or not isinstance(p_old, (int, float)):
                out[key] = w
            elif p_new >= p_old:
                out[key] = w
    return out

def save(rl):
    """Funde con lo guardado y reescribe el archivo. Devuelve lo que quedó.

    El candado es un archivo aparte, no el propio `pet-usage.json`: la escritura
    es atómica (`os.replace`), o sea que el inodo cambia en cada pasada y un
    candado sobre él no protegería al siguiente. Si otra sesión lo tiene cogido,
    esta pasada no escribe: la otra está guardando la misma verdad y en diez
    segundos volvemos a pasar por aquí.

    Un `.tmp` por PID para que dos sesiones no se pisen el archivo intermedio.
    """
    fd = None
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_RDWR, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return None                   # otra sesión está escribiendo
        old = {}
        try:
            with open(OUT) as f:
                old = json.load(f) or {}
        except Exception:
            pass                          # no hay archivo aún, o está a medio escribir
        prev = old.get("rate_limits")
        rl = merge(rl, prev)

        now = int(time.time() * 1000)
        # `written_at_ms` dice cuándo pasamos por aquí: se sella cada vez, cada
        # ~10 s, y por eso sirve para saber si hay una sesión viva. Lo que NO
        # dice es si las cifras son recientes: Claude Code las refresca a saltos,
        # así que el archivo puede llevar media hora "fresco" con un porcentaje
        # de hace diez minutos. `changed_at_ms` es esa segunda señal: solo avanza
        # cuando los números se mueven de verdad.
        changed = now if rl != prev else old.get("changed_at_ms")
        if not isinstance(changed, (int, float)):
            changed = now                 # primera pasada, o archivo de una versión vieja
        tmp = f"{OUT}.{os.getpid()}.tmp"
        with open(tmp, "w") as f:
            json.dump({"rate_limits": rl, "written_at_ms": now,
                       "changed_at_ms": int(changed)}, f)
        os.replace(tmp, OUT)              # escritura atómica
        return rl
    except Exception:
        return None
    finally:
        if fd is not None:
            os.close(fd)                  # soltar el candado


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        print("🐱 —")
        return
    # JSON válido pero que no es un objeto (una lista, un número): `data.get`
    # reventaría y el traceback saldría en la línea de estado de Claude Code.
    if not isinstance(data, dict):
        print("🐱 —")
        return

    rl = data.get("rate_limits")
    if not isinstance(rl, dict):
        rl = {}

    if rl:
        rl = save(rl) or rl

    def used(key):
        w = rl.get(key)
        return w.get("used_percentage") if isinstance(w, dict) else None

    def pct(key):
        v = used(key)
        return f"{round(v)}%" if isinstance(v, (int, float)) else "–"

    def face(key):
        v = used(key)
        if not isinstance(v, (int, float)): return "🫥"
        return "😺" if v < 40 else "😼" if v < 70 else "🙀" if v < 90 else "😿"

    def field(name, key):
        d = data.get(name)
        return (d.get(key) or "") if isinstance(d, dict) else ""

    model = field("model", "display_name")
    cwd = os.path.basename(field("workspace", "current_dir"))

    parts = [f"{face('five_hour')} {pct('five_hour')} · 📅 {pct('seven_day')}"]
    if model: parts.append(model)
    if cwd:   parts.append(cwd)
    print("  ".join(parts))

main()
