#!/bin/bash
# Empaqueta ClaudePet.app en un .zip para compartir.
#
# OJO: la app va firmada "adhoc" (sin cuenta de desarrollador de Apple), así que
# a quien la reciba Gatekeeper se la va a bloquear. Ver INSTALAR.md.
# Si quien la recibe sabe usar la terminal, es MÁS fácil que se clone el repo
# y corra ./build.sh: al compilarla en su propia máquina no hay cuarentena.
set -euo pipefail
cd "$(dirname "$0")"

./build.sh

VERSION=$(plutil -extract CFBundleShortVersionString raw ClaudePet.app/Contents/Info.plist)
OUT="ClaudePet-$VERSION.zip"

rm -f "$OUT"
# ditto conserva los metadatos del bundle; `zip` a secas rompe la firma.
ditto -c -k --sequesterRsrc --keepParent ClaudePet.app "$OUT"

echo ""
echo "📦 $OUT  ($(du -h "$OUT" | cut -f1))"
echo ""
echo "Dile a quien lo reciba que, tras descomprimir, corra esto una vez:"
echo "    xattr -dr com.apple.quarantine /ruta/a/ClaudePet.app"
echo "…o que lo abra desde Ajustes → Privacidad y seguridad → «Abrir igualmente»."
