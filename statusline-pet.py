#!/usr/bin/env python3
"""
Hook de statusLine para Claude Code.
Guarda el bloque `rate_limits` en ~/.claude/pet-usage.json (para Claude Pet)
e imprime una línea de estado. No consume cuota: corre 100% local.
"""
import json, os, sys, time

HOME = os.path.expanduser("~")
OUT = os.path.join(HOME, ".claude", "pet-usage.json")

def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        print("🐱 —")
        return

    rl = data.get("rate_limits") or {}

    if rl:
        try:
            tmp = OUT + ".tmp"
            with open(tmp, "w") as f:
                json.dump({"rate_limits": rl, "written_at_ms": int(time.time() * 1000)}, f)
            os.replace(tmp, OUT)          # escritura atómica
        except Exception:
            pass

    def pct(key):
        v = (rl.get(key) or {}).get("used_percentage")
        return f"{round(v)}%" if isinstance(v, (int, float)) else "–"

    def face(key):
        v = (rl.get(key) or {}).get("used_percentage")
        if not isinstance(v, (int, float)): return "🫥"
        return "😺" if v < 40 else "😼" if v < 70 else "🙀" if v < 90 else "😿"

    model = (data.get("model") or {}).get("display_name", "")
    cwd = os.path.basename((data.get("workspace") or {}).get("current_dir", "") or "")

    parts = [f"{face('five_hour')} {pct('five_hour')} · 📅 {pct('seven_day')}"]
    if model: parts.append(model)
    if cwd:   parts.append(cwd)
    print("  ".join(parts))

main()
