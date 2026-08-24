#!/usr/bin/env bash
# Instala Claude Pet en Ubuntu/Debian desde el código fuente.
# Genera el .deb, lo instala con apt e instala el hook de statusLine.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "  🦞 Claude Pet — Ubuntu"
echo "  ─────────────────────────────────────────────"

# ── 1. Generar el .deb ───────────────────────────────────────
echo "  Generando el paquete desde el código fuente…"
python3 "$HERE/linux/build-deb.py"
DEB="$(ls -t "$HERE"/dist/claudepet_*.deb 2>/dev/null | head -1)"
if [ -z "$DEB" ]; then
  echo "  ❌ No se generó el .deb. Revisa los errores anteriores."
  exit 1
fi
echo "  Paquete listo: $DEB"

# ── 2. Instalar ───────────────────────────────────────────────
echo "  Instalando (puede pedir contraseña)…"
sudo apt install -y "$DEB"

# ── 3. Arrancar ───────────────────────────────────────────────
claudepet &
sleep 2
echo "  ✅ Clawd está en la bandeja del sistema."

# ── 4. Hook de statusLine ────────────────────────────────────
echo ""
echo "  Para que Clawd muestre tu cuota hace falta el hook de statusLine."
echo "  (Sin él puede quedarse con datos de hasta hace ~15 min.)"
read -r -p "  ¿Lo instalo ahora? [S/n] " H
case "$H" in
  [nN]) echo "  Vale. Puedes instalarlo luego con: claudepet --install-statusline" ;;
  *)
    claudepet --install-statusline
    echo "  ⚠️  Reinicia Claude Code para que empiece a escribir los datos."
    ;;
esac

echo ""
echo "  Para desinstalar: sudo apt remove claudepet"
echo ""
