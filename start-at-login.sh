#!/bin/bash
# Activa el arranque al iniciar sesión.
#
# Usa SMAppService (la API nativa de macOS 13+), no AppleScript: no pide
# ningún permiso. También se puede activar desde el panel de la app, o
# quitar a mano en Ajustes → General → Ítems de inicio.
set -euo pipefail
APP="$(cd "$(dirname "$0")" && pwd)/ClaudePet.app"

if [ ! -d "$APP" ]; then
  echo "❌ No encuentro ClaudePet.app. Corre primero ./build.sh"; exit 1
fi

if [ "${1:-}" = "--off" ]; then
  "$APP/Contents/MacOS/ClaudePet" --login-off
  exit 0
fi

"$APP/Contents/MacOS/ClaudePet" --login-on
echo "   Para desactivarlo: ./start-at-login.sh --off  (o el interruptor del panel)"
