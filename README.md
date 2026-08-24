# 🦞 Claude Pet

**Clawd**, la mascota de Claude Code, vigilando tu consumo de cuota desde la barra de
menús y como bicho flotante en el escritorio. Cambia de cara según cuánto llevas gastado.

**No consume tu cuota**: lee los datos de archivos locales que Claude Code ya escribe en
tu máquina (`~/.claude.json` y `~/.claude/pet-usage.json`). Sin red.

## Instalar

### macOS

Con Claude Code, desde el repo:

```
/instalar-claude-pet
```

Detecta el sistema, compila/instala e instala el hook de `statusLine` si falta.

A mano:

```bash
./build.sh          # compila (basta con Command Line Tools, no hace falta Xcode)
open ClaudePet.app  # arranca
```

También hay un ejecutable ya empaquetado en [`dist/ClaudePet-1.0.zip`](dist/) —
descomprimir y `bash install.sh`. Va firmado *ad-hoc*, sin cuenta de desarrollador de
Apple, así que el instalador tiene que retirarle la cuarentena: si prefieres no confiar
en un binario que no puedes verificar, compílalo tú con `./build.sh` — el resultado es
el mismo y no pasa por Gatekeeper.

### Ubuntu

```bash
sudo apt install ./dist/claudepet_1.2_all.deb
claudepet &
```

Versión en Python con applet de bandeja: ver [`linux/README.md`](linux/README.md). La app
de macOS no se puede portar (SwiftUI, AppKit y compañía son exclusivos de Darwin).
Las versiones de macOS y Linux avanzan por separado.

### Verificar los binarios de `dist/`

```
7f7972f7c53ac8a0e2fe7007e88147cbc6685dbf80d5da724fd1c0b0a82f2c14  ClaudePet-1.0.zip
8e5c5a4d7f81f2f97425ccbbd8d92b443e45edc98398d2e869fad16d7e8c3622  claudepet_1.2_all.deb
```

```bash
shasum -a 256 dist/*        # macOS
sha256sum dist/*            # Linux
```

Se regeneran con `./package.sh` y `python3 linux/build-deb.py`; el hash cambia con cada
compilación, así que si no coincide, compila desde el fuente en vez de fiarte.

## El hook de `statusLine` (recomendado)

Si Clawd muestra `0/0 %`, falta el hook: `~/.claude.json` solo se actualiza cuando Claude
Code quiere (se ha medido una vez en 22 minutos), así que como fuente única no basta.

```bash
./install-statusline.sh    # configura el hook
./uninstall-statusline.sh  # revertirlo
```

Es gratis: Claude Code ejecuta un script local (`statusline-pet.py`), sin tokens ni red.
Hace copia de seguridad de `~/.claude/settings.json` y avisa si ya tenías otro `statusLine`.

**Reinicia Claude Code después de instalarlo.** El `statusLine` se lee al arrancar; hasta
entonces no se escribe `pet-usage.json` y seguirás viendo `0/0 %`.

Si pasan 15 minutos sin datos frescos (y Claude Code está corriendo), la app lo avisa: el
badge se pone gris con un ⏱ y el panel marca la antigüedad.

> **Si sigues en `0/0 %` con el hook instalado**, mira si ese proyecto tiene su propio
> `statusLine` en `.claude/settings.json` o `.claude/settings.local.json`: las settings
> del proyecto ganan sobre `~/.claude/settings.json`, que es donde escribe el instalador,
> y ahí el hook no llega a ejecutarse. `--dump` te lo dice desde el directorio en cuestión.

## Permisos

Sin red, sin Automatización, sin Accesibilidad, sin acceso a archivos protegidos. Solo
lee dos archivos del home. Detalle en [INSTALAR.md](INSTALAR.md).

Lo único que puede preguntar:

- **Notificaciones**, una vez, y solo cuando haya algo que avisar (al cruzar el 50 %).
- **Ítems de inicio**, si activas «Abrir al iniciar sesión» (vía `SMAppService`, sin diálogo).

```bash
ClaudePet.app/Contents/MacOS/ClaudePet --dump   # diagnóstico: permisos, fuentes y cifras
```

## Uso

- **Barra de menús** → `😺 25%`. Clic abre el panel con las barras, los reinicios y los ajustes.
- **Mascota de escritorio** → arrástrala donde quieras; pasa el mouse para ver el detalle.
- **Clic sobre Clawd** → sonríe y relee el archivo.
- **Clic derecho** → ocultar del escritorio, actualizar ahora, disparar una actividad,
  apagar las actividades automáticas, traerla a esta pantalla, salir.
- **Notificaciones** al cruzar 50 %, 70 % y 90 %.

La mascota lleva dos anillos: el exterior es la semana (7 días) y el interior la sesión
(5 h). El badge muestra `sesión/semana`.

| Consumo | Anillo |
|---|---|
| < 40 % | verde |
| 40–70 % | amarillo |
| 70–90 % | naranja |
| ≥ 90 % | rojo |
| sin datos | gris |

Cada 45–150 s Clawd hace algo unos segundos (café, bostezo, baile, ejercicio, siesta,
manzana) y vuelve al reposo. Entre las 6 p.m. y las 6 a.m. lleva gorrito de dormir.

```bash
./ClaudePet.app/Contents/MacOS/ClaudePet --demo        # recorre las actividades en bucle
./ClaudePet.app/Contents/MacOS/ClaudePet --demo=nap    # fija una sola
```

### Planes Team y Enterprise

Se miden en dinero, no en porcentaje. La app dibuja todas las dimensiones que encuentre
(gasto, créditos, ventanas del plan) y calcula el humor sobre la peor de todas. Si la
sesión no usa una suscripción de Claude.ai (API key, Bedrock, Vertex) no hay límites que
mostrar y la app lo dice.

Para probar con datos de otro plan sin tocar los tuyos:

```bash
CLAUDEPET_JSON=/ruta/a/otro.json CLAUDEPET_STATUSLINE_JSON=/nope \
  ClaudePet.app/Contents/MacOS/ClaudePet --dump
```

## Estructura

```
Sources/main.swift       todo el código de macOS (modelo, lectura local, UI, ventana flotante)
build.sh                 compila y empaqueta ClaudePet.app
package.sh               genera el .zip para compartir
statusline-pet.py        hook opcional de statusLine
install-statusline.sh    instala/revierte el hook
uninstall-statusline.sh
start-at-login.sh        arrancar al iniciar sesión (--off para quitarlo)
linux/                   versión para Ubuntu (Python) y su paquete .deb
```
