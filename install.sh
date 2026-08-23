#!/bin/bash
# Instalador de Claude Pet.
#
# Existe por una razón concreta: la app va firmada ad-hoc (sin cuenta de
# desarrollador de Apple), así que si llega por descarga, macOS le pone el
# atributo de cuarentena y al abrirla NO ofrece ningún botón para continuar
# — solo "Mover a la papelera". Este script quita ese atributo, que es
# justo lo que harías a mano, y deja la app lista.
#
# Un script invocado a propósito desde la Terminal no pasa por Gatekeeper,
# por eso esto funciona donde el doble clic no.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="ClaudePet.app"
# Se puede redirigir con CLAUDEPET_DEST (útil para probar o instalar en ~/Applications).
DEST="${CLAUDEPET_DEST:-/Applications/$APP_NAME}"

echo ""
echo "  🦞 Claude Pet"
echo "  ─────────────────────────────────────────────"

# ── 1. Localizar la app ───────────────────────────────────────
SRC=""
if   [ -d "$HERE/$APP_NAME" ];             then SRC="$HERE/$APP_NAME"
elif [ -d "$HERE/../$APP_NAME" ];          then SRC="$(cd "$HERE/.." && pwd)/$APP_NAME"
else
  ZIP="$(ls "$HERE"/ClaudePet-*.zip 2>/dev/null | head -1 || true)"
  if [ -n "$ZIP" ]; then
    echo "  Descomprimiendo $(basename "$ZIP")…"
    ditto -x -k "$ZIP" "$HERE"
    SRC="$HERE/$APP_NAME"
  fi
fi

if [ -z "$SRC" ] || [ ! -d "$SRC" ]; then
  echo "  ❌ No encuentro $APP_NAME junto a este script."
  echo "     Ponlo en la misma carpeta y vuelve a correrlo."
  exit 1
fi

# ── 2. Instalar ───────────────────────────────────────────────
if [ -d "$DEST" ]; then
  read -r -p "  Ya hay una versión en $(dirname "$DEST"). ¿La reemplazo? [s/N] " R
  case "$R" in [sS]|[yY]) ;; *) echo "  Cancelado."; exit 0 ;; esac
  pkill -f "$DEST/Contents/MacOS/ClaudePet" 2>/dev/null || true
  rm -rf "$DEST"
fi

echo "  Copiando a $(dirname "$DEST")…"
ditto "$SRC" "$DEST"

# ── 3. Quitar la cuarentena ───────────────────────────────────
xattr -dr com.apple.quarantine "$DEST" 2>/dev/null || true
echo "  Cuarentena retirada."

# ── 4. Arrancar ───────────────────────────────────────────────
open "$DEST"
sleep 2

echo ""
echo "  ✅ Listo. Clawd está en tu barra de menús, arriba a la derecha."
echo ""
echo "  Lo que esta app hace y no hace:"
echo "    · Lee dos archivos tuyos: ~/.claude.json y ~/.claude/pet-usage.json"
echo "    · NO usa red, cámara, micrófono, ubicación ni Accesibilidad"
echo "    · NO consume tu cuota de Claude Code al leerla"
echo "    · Solo te pedirá permiso de notificaciones, y únicamente si"
echo "      algún día llegas al 50 % de tu límite"
echo ""

read -r -p "  ¿Que arranque sola al iniciar sesión? [s/N] " L
case "$L" in
  [sS]|[yY]) "$DEST/Contents/MacOS/ClaudePet" --login-on ;;
  *) echo "  Vale. Se puede activar luego desde el panel de la app." ;;
esac

echo ""
echo "  Para desinstalar:  rm -rf $DEST"
echo ""
