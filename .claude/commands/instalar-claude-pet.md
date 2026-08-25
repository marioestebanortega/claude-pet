---
description: Instala Claude Pet (macOS, Ubuntu o Windows, según el sistema) y configura el hook de statusLine si falta
---

Instala **Claude Pet** en esta máquina de principio a fin. Detecta el sistema
operativo y aplica la ruta correcta, y deja el **hook de `statusLine`** configurado
—que es lo que hace que la mascota muestre cifras reales en vez de `0/0 %`—.

Trabaja desde la raíz del repo (donde están `build.sh`, `install-statusline.sh` y
`linux/`). Ve informando de cada paso y, al final, da un resumen claro.

## 0. Detectar el sistema
**No ejecutes `uname` a ciegas.** Mira primero el bloque de entorno que Claude Code ya
te da en el contexto: la línea `Platform` dice `darwin`, `linux` o `win32`, y eso no
cuesta ningún comando.

Si no lo tienes a mano, `uname -s` sirve **solo si existe**:

- `Darwin` → sección **macOS**.
- `Linux` → sección **Ubuntu/Linux**.
- `MINGW64_NT-*`, `MINGW32_NT-*`, `MSYS_NT-*`, `CYGWIN_NT-*` → sección **Windows**. Eso
  es Git Bash, MSYS2 o Cygwin corriendo *encima* de Windows, no un Linux: el instalador
  que hay que usar es el de PowerShell, no el `.sh`.
- **`uname` no existe** → estás en PowerShell o en `cmd`, o sea Windows. Confírmalo con
  `$PSVersionTable.PSVersion` y sigue por **Windows**.

## 1a. macOS
1. Comprueba el compilador: `xcrun --find swiftc`. Si falla, dile al usuario que
   instale las Command Line Tools con `xcode-select --install` y **detente** (no
   sigas hasta que las tenga).
2. Compila y arranca: `./build.sh && open ClaudePet.app`.
   (Compilar en la propia máquina evita la cuarentena de Gatekeeper — no hay que
   tocar `xattr` ni "Abrir igualmente".)
3. Verifica que corre: `pgrep -x ClaudePet` debe devolver un PID.

## 1b. Ubuntu/Linux
1. Genera e instala desde el fuente con `./install-linux.sh`.
   El script llama a `python3 linux/build-deb.py` (genera el `.deb`),
   lo instala con `apt` (resuelve las dependencias GTK/AppIndicator solo)
   e instala el hook de statusLine opcionalmente.
   No hay `.deb` precompilado en el repo: siempre se genera en el momento.
2. Si preferís correrlo sin instalar:
   `cd linux && python3 -m claudepet &` (necesita `python3-gi`, `python3-gi-cairo`,
   `gir1.2-gtk-3.0` y un indicador de bandeja Ayatana/AppIndicator).

## 1c. Windows
1. Instala desde el fuente, sin administrador:
   `powershell -ExecutionPolicy Bypass -File .\install-windows.ps1`
   El `-ExecutionPolicy Bypass` no es opcional: el valor por defecto en Windows 11 es
   `Restricted` y no deja ejecutar ningún script, ni siquiera uno local.
2. Si no hay Python, el instalador lo pone él con
   `winget install -e --id Python.Python.3.13 -s winget --scope user`.
   **Cuidado con la detección**: en `%LOCALAPPDATA%\Microsoft\WindowsApps` hay un
   `python.exe` de cero bytes que es un alias de la Microsoft Store. Existe y sale en el
   PATH, pero no es Python: al ejecutarlo abre la tienda. No des por instalado Python
   solo porque `where python` conteste algo.
3. Verifica que corre:
   `Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" | Where-Object { $_.CommandLine -match 'claudepet' }`
4. Avísale de que **Windows 11 esconde los iconos nuevos de la bandeja** detrás de la
   flecha `^` de la esquina. No es un fallo de la app, y es la primera duda de todo el
   mundo. La mascota del escritorio sí se ve.

## 2. Hook de statusLine (en LOS TRES sistemas) — el paso que suele faltar
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
     - Windows (instalado): `claudepet --install-statusline`
     - Windows (desde fuente): `cd windows; python -X utf8 -m claudepet --install-statusline`

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
  - Windows: `claudepet --dump` (o `python -X utf8 -m claudepet --dump` desde `windows\`)
- Resume en 4-5 líneas: qué instalaste, si el hook ya estaba o lo pusiste tú, el
  recordatorio de reiniciar Claude Code, y cómo desinstalar
  (`./uninstall-statusline.sh` para el hook; borrar la app, `sudo apt remove claudepet`
  o `install-windows.ps1 off` para el resto).

Si algo falla (compilador ausente, `sudo` denegado, sin bandeja del sistema en Linux,
Python ausente o política de ejecución bloqueada en Windows), explica qué pasó y qué
necesita el usuario para continuar; no lo dejes a medias en silencio.
