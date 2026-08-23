#!/bin/bash
# Hace que Claude Pet arranque solo al iniciar sesión.
APP="$(cd "$(dirname "$0")" && pwd)/ClaudePet.app"
osascript <<OSA
tell application "System Events"
  if not (exists login item "ClaudePet") then
    make login item at end with properties {path:"$APP", hidden:true}
  end if
end tell
OSA
echo "✅ Claude Pet arrancará al iniciar sesión."
echo "   Para quitarlo: Ajustes → General → Ítems de inicio."
