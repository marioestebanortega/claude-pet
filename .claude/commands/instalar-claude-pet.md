---
description: Instala Claude Pet (macOS o Ubuntu, según el sistema) y configura el hook de statusLine si falta
---

Instala **Claude Pet** en esta máquina de principio a fin. Detecta el sistema
operativo y aplica la ruta correcta, y deja el **hook de `statusLine`** configurado
—que es lo que hace que la mascota muestre cifras reales en vez de `0/0 %`—.

Trabaja desde la raíz del repo (donde están `build.sh`, `install-statusline.sh` y
`linux/`). Ve informando de cada paso y, al final, da un resumen claro.

## 0. Detectar el sistema
Ejecuta `uname -s`:
- `Darwin` → sigue la sección **macOS**.
- `Linux` → sigue la sección **Ubuntu/Linux**.

## 1a. macOS
1. Comprueba el compilador: `xcrun --find swiftc`. Si falla, dile al usuario que
   instale las Command Line Tools con `xcode-select --install` y **detente** (no
   sigas hasta que las tenga).
2. Compila y arranca: `./build.sh && open ClaudePet.app`.
   (Compilar en la propia máquina evita la cuarentena de Gatekeeper — no hay que
   tocar `xattr` ni "Abrir igualmente".)
3. Verifica que corre: `pgrep -x ClaudePet` debe devolver un PID.

## 1b. Ubuntu/Linux
1. Si hay `apt` y existe el `.deb`, instálalo (resuelve solas las dependencias
   GTK/AppIndicator): `sudo apt install ./dist/claudepet_1.3_all.deb` y luego
   lánzalo con `claudepet &`.
2. Si no quieres usar el `.deb`, córrelo desde la fuente:
   `cd linux && python3 -m claudepet &` (necesita `python3-gi`, `python3-gi-cairo`,
   `gir1.2-gtk-3.0` y un indicador de bandeja Ayatana/AppIndicator).

## 2. Hook de statusLine (en AMBOS sistemas) — el paso que suele faltar
El hook es lo que da el dato fresco; sin él la mascota suele quedarse en `0/0 %`.
**No es un requisito estricto** (la app funciona si `~/.claude.json` ya trae
`cachedUsageUtilization`), pero ese caché suele estar ausente o viejo, así que en
la práctica hace falta. Comprueba e instala:

1. Mira si ya está: lee `~/.claude/settings.json` y comprueba si
   `statusLine.command` termina en `statusline-pet.py`.
   - Si **ya es el nuestro** → no toques nada, avisa que ya estaba.
   - Si **no hay** statusLine, o es **de otro** → instálalo (los instaladores hacen
     copia de seguridad y preservan un statusLine ajeno en un sidecar restaurable):
     - macOS: `./install-statusline.sh`
     - Linux (por `.deb`): `claudepet --install-statusline`
     - Linux (desde fuente): `cd linux && python3 -m claudepet --install-statusline`

2. **Comprueba también las settings del proyecto**, que son las que mandan: lee
   `.claude/settings.local.json` y `.claude/settings.json` del directorio actual (en
   ese orden; gana la primera que traiga un `statusLine`). Los instaladores solo
   escriben en `~/.claude/settings.json`, así que un `statusLine` de proyecto —
   propio o venido en el repo del equipo — **deja el hook sin ejecutarse aquí aunque
   la instalación haya ido bien**, y la mascota se queda en `0/0 %` sin que nada lo
   explique.
   - Si el que gana es el nuestro → todo en orden.
   - Si es ajeno → **dilo antes de dar la instalación por buena**: en este proyecto
     el hook no correrá. Las salidas son quitarlo de las settings del proyecto, o
     hacer que ese comando llame también a `~/.claude/statusline-pet.py`.

## 3. Recordar reiniciar Claude Code
El `statusLine` se carga **al arrancar** Claude Code. Dile claramente al usuario que
**reinicie Claude Code** para que el hook empiece a escribir los datos; hasta
entonces la mascota puede seguir en `0/0 %`.

## 4. Verificar y resumir
- Comprueba qué está leyendo la app:
  - macOS: `ClaudePet.app/Contents/MacOS/ClaudePet --dump`
  - Linux: `python3 -m claudepet --dump` (o `claudepet --dump`)
- Resume en 4-5 líneas: qué instalaste, si el hook ya estaba o lo pusiste tú, el
  recordatorio de reiniciar Claude Code, y cómo desinstalar
  (`./uninstall-statusline.sh` para el hook; borrar la app / `sudo apt remove
  claudepet` para el resto).

Si algo falla (compilador ausente, `sudo` denegado, sin bandeja del sistema en
Linux), explica qué pasó y qué necesita el usuario para continuar; no lo dejes a
medias en silencio.
