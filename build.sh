#!/bin/bash
# Compila ClaudePet y lo empaqueta como ClaudePet.app (no necesita Xcode completo)
set -euo pipefail
cd "$(dirname "$0")"

APP="ClaudePet.app"
BIN="$APP/Contents/MacOS/ClaudePet"

if ! xcrun --find swiftc >/dev/null 2>&1; then
  echo "❌ Falta el compilador de Swift."
  echo "   Instala las Command Line Tools (gratis, ~1 GB, no hace falta Xcode entero):"
  echo "       xcode-select --install"
  exit 1
fi

echo "→ Compilando…"
rm -rf "$APP" build
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

swiftc -O -parse-as-library Sources/main.swift -o "$BIN"

cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>            <string>ClaudePet</string>
  <key>CFBundleDisplayName</key>     <string>Claude Pet</string>
  <key>CFBundleExecutable</key>      <string>ClaudePet</string>
  <key>CFBundleIdentifier</key>      <string>com.mario.claudepet</string>
  <key>CFBundlePackageType</key>     <string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundleVersion</key>         <string>1</string>
  <key>LSMinimumSystemVersion</key>  <string>13.0</string>
  <key>LSUIElement</key>             <true/>
  <key>NSHighResolutionCapable</key> <true/>
</dict>
</plist>
PLIST

codesign --force --sign - "$APP" 2>/dev/null || true

echo "✅ Listo: $(pwd)/$APP"
