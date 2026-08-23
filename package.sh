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
# Se empaquetan juntos la app y el instalador: sin el instalador, a quien la
# reciba macOS solo le ofrece "Mover a la papelera".
STAGE=$(mktemp -d)
ditto ClaudePet.app "$STAGE/ClaudePet.app"
cp install.sh "$STAGE/install.sh"
cp INSTALAR.md "$STAGE/LEEME.md"

# ditto conserva los metadatos del bundle; `zip` a secas rompe la firma.
ditto -c -k --sequesterRsrc "$STAGE" "$OUT"
rm -rf "$STAGE"

echo ""
echo "📦 $OUT  ($(du -h "$OUT" | cut -f1))"
echo ""
echo "Dile a quien lo reciba: descomprimir y, en la Terminal, correr"
echo "    bash ~/Downloads/install.sh"
echo ""
echo "Es UN paso. Si en cambio hace doble clic en la app, macOS solo le"
echo "ofrecerá «Mover a la papelera»: la firma es ad-hoc, sin Developer ID."
