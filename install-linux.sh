#!/usr/bin/env bash
# Instala Claude Pet en Ubuntu/Debian desde el código fuente.
#
#   ./install-linux.sh --user     en ~/.local, sin root — lo normal
#   ./install-linux.sh --user off lo quita de ~/.local
#   ./install-linux.sh            .deb con apt, en /usr — pide la contraseña una vez
#
# La app nunca necesita root, ni para instalarse ni para funcionar: todo lo que
# escribe está en tu HOME (~/.config/claudepet/state.json y ~/.config/autostart)
# y de ~/.claude.json solo lee. El `sudo` del último modo no es de la app: es
# `apt`, que escribe en /usr y en la base de datos de dpkg.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
PREFIX="$HOME/.local"
LIB="$PREFIX/lib/claudepet"

MODO=deb
ACCION=on
case "${1:-}" in
  --user) MODO=user; [ "${2:-}" = "off" ] && ACCION=off ;;
  "")     ;;
  *)      echo "Uso: $0 [--user [off]]"; exit 1 ;;
esac

echo ""
echo "  🦞 Claude Pet — Ubuntu"
echo "  ─────────────────────────────────────────────"

# ── Quitar la instalación de usuario ─────────────────────────
if [ "$MODO" = user ] && [ "$ACCION" = off ]; then
  pkill -f "^python3 -m claudepet" 2>/dev/null || true
  rm -rf "$LIB" \
         "$PREFIX/bin/claudepet" \
         "$PREFIX/share/applications/claudepet.desktop" \
         "$PREFIX"/share/icons/hicolor/*/apps/claudepet.png \
         "$HOME/.config/autostart/claudepet.desktop"
  echo "  ✅ Desinstalado de ~/.local."
  echo "     Tus ajustes siguen en ~/.config/claudepet/ por si vuelves;"
  echo "     para borrarlos también: rm -rf ~/.config/claudepet"
  echo ""
  exit 0
fi

# ── Instalación de usuario, sin root ─────────────────────────
if [ "$MODO" = user ]; then
  echo "  Instalando en $PREFIX (sin root)…"

  # Mismo reparto que el .deb, pero bajo ~/.local: el paquete Python en
  # lib/claudepet/claudepet y el hook a su lado, que es donde lo busca
  # `--install-statusline` (ver `_hook_source` en __main__.py).
  mkdir -p "$LIB/claudepet" "$PREFIX/bin" "$PREFIX/share/applications"
  cp "$HERE"/linux/claudepet/*.py "$LIB/claudepet/"
  cp "$HERE"/statusline-pet.py "$LIB/statusline-pet.py"
  chmod 755 "$LIB/statusline-pet.py"

  cat > "$PREFIX/bin/claudepet" <<EOF
#!/bin/sh
# Lanzador de Claude Pet (instalación de usuario)
PYTHONPATH="$LIB\${PYTHONPATH:+:\$PYTHONPATH}"
export PYTHONPATH
exec python3 -m claudepet "\$@"
EOF
  chmod 755 "$PREFIX/bin/claudepet"

  cat > "$PREFIX/share/applications/claudepet.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Claude Pet
Comment=Vigila tu consumo de Claude Code
Exec=$PREFIX/bin/claudepet
Icon=claudepet
Terminal=false
Categories=Utility;Development;
Keywords=claude;usage;quota;
EOF

  # El icono, generado con el mismo sprite que usa el .deb.
  for PX in 48 64 128; do
    D="$PREFIX/share/icons/hicolor/${PX}x${PX}/apps"
    mkdir -p "$D"
    PYTHONPATH="$HERE/linux" python3 -c "
import sys
from claudepet import sprite
open(sys.argv[1], 'wb').write(sprite.render(cell=max(1, int(sys.argv[2]) // 11)))
" "$D/claudepet.png" "$PX"
  done

  # Que el menú de aplicaciones se entere sin cerrar sesión.
  update-desktop-database "$PREFIX/share/applications" 2>/dev/null || true
  gtk-update-icon-cache -qtf "$PREFIX/share/icons/hicolor" 2>/dev/null || true

  echo "  ✅ Instalado en $PREFIX — no se ha usado root en ningún momento."

  # Ubuntu añade ~/.local/bin al PATH desde ~/.profile, pero solo si el
  # directorio ya existía al iniciar sesión: si lo acabamos de crear, en esta
  # sesión todavía no está.
  case ":$PATH:" in
    *":$PREFIX/bin:"*) ;;
    *) echo ""
       echo "  ⚠️  $PREFIX/bin no está en tu PATH en esta sesión."
       echo "     Para esta terminal:  export PATH=\"\$HOME/.local/bin:\$PATH\""
       echo "     (al reiniciar sesión Ubuntu lo añade solo)" ;;
  esac
else
  # ── El .deb, para toda la máquina ───────────────────────────
  echo "  Modo apt: instala en /usr para todos los usuarios y pide la contraseña."
  echo "  Si solo lo quieres para ti, esto no hace falta:  $0 --user"
  echo ""
  echo "  Generando el paquete desde el código fuente…"
  python3 "$HERE/linux/build-deb.py"
  DEB="$(ls -t "$HERE"/dist/claudepet_*.deb 2>/dev/null | head -1)"
  if [ -z "$DEB" ]; then
    echo "  ❌ No se generó el .deb. Revisa los errores anteriores."
    exit 1
  fi
  echo "  Paquete listo: $DEB"
  echo "  Instalando con apt (pedirá la contraseña)…"
  sudo apt install -y "$DEB"
fi

# ── Arrancar ─────────────────────────────────────────────────
if pgrep -f "claudepet" >/dev/null 2>&1; then
  echo "  ℹ️  Ya hay un Claude Pet corriendo; no arranco otro."
  echo "     Para que tome esta versión: pkill -f claudepet && claudepet &"
else
  if [ "$MODO" = user ]; then "$PREFIX/bin/claudepet" & else claudepet & fi
  sleep 2
  echo "  ✅ Clawd está en la bandeja del sistema."
fi

CLAUDEPET=claudepet
[ "$MODO" = user ] && CLAUDEPET="$PREFIX/bin/claudepet"

# ── Hook de statusLine ───────────────────────────────────────
echo ""
echo "  Para que Clawd muestre tu cuota hace falta el hook de statusLine."
echo "  (Sin él puede quedarse con datos de hasta hace ~15 min.)"
read -r -p "  ¿Lo instalo ahora? [S/n] " H
case "$H" in
  [nN]) echo "  Vale. Puedes instalarlo luego con: $CLAUDEPET --install-statusline" ;;
  *)
    "$CLAUDEPET" --install-statusline
    echo "  ⚠️  Reinicia Claude Code para que empiece a escribir los datos."
    ;;
esac

echo ""
if [ "$MODO" = user ]; then
  echo "  Para desinstalar: $0 --user off"
else
  echo "  Para desinstalar: sudo apt remove claudepet"
fi
echo ""
