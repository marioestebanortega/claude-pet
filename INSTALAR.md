# Instalar Claude Pet

## Qué permisos pide

**Casi ninguno**, y eso es a propósito:

| Permiso | ¿Lo pide? |
|---|---|
| Archivos | **No.** Solo lee `~/.claude.json` y `~/.claude/pet-usage.json`. El home no está protegido por TCC (a diferencia de Escritorio, Documentos y Descargas), así que macOS no pregunta nada. |
| Red | **No.** La app nunca abre una conexión. |
| Automatización / AppleScript | **No.** |
| Accesibilidad | **No.** |
| Grabación de pantalla | **No.** |
| Cámara, micrófono, ubicación, contactos… | **No.** |
| **Notificaciones** | Sí, **una vez** — y solo la primera vez que de verdad haya algo que avisar (al cruzar el 50 %). Si nunca llegas ahí, nunca te pregunta. |
| **Ítems de inicio** | Solo si activas «Abrir al iniciar sesión». Usa `SMAppService`, la API nativa: no muestra ningún diálogo y se quita desde Ajustes → General → Ítems de inicio. |

Para verificarlo en cualquier momento:

```bash
ClaudePet.app/Contents/MacOS/ClaudePet --dump
```

(La tabla de arriba es de macOS: TCC, Automatización y compañía son cosa de Darwin.)

---

## En Ubuntu

La versión de Linux se instala **sin root**:

```bash
./install-linux.sh --user        # en ~/.local, sin sudo
./install-linux.sh --user off    # y así se quita
```

No pide permisos de administrador ni para instalarse ni para funcionar: escribe solo en
`~/.config/claudepet/` y `~/.config/autostart`, y de `~/.claude.json` solo lee. El aviso
de la consulta automática sale por `notify-send`, que tampoco pide autorización.

Hay un segundo camino, el `.deb` gestionado por `apt`, que sí pide la contraseña una vez
—no por la app, sino porque `apt` escribe en `/usr`—. Elígelo solo si lo quieres para
todos los usuarios de la máquina. Detalle en [`linux/README.md`](linux/README.md).

---

## En Windows

También **sin administrador**:

```powershell
powershell -ExecutionPolicy Bypass -File .\install-windows.ps1
powershell -ExecutionPolicy Bypass -File .\install-windows.ps1 off
```

El `-ExecutionPolicy Bypass` no es un truco para saltarse nada: el valor por defecto en
Windows 11 es `Restricted`, que no deja ejecutar **ningún** script, ni siquiera uno tuyo
guardado en tu propio disco.

**Qué escribe**: `%LOCALAPPDATA%\Programs\ClaudePet` (la app), `%APPDATA%\ClaudePet`
(los ajustes), los dos accesos directos del menú Inicio y del arranque automático, y una
entrada en `HKCU\Environment` para poder escribir `claudepet` en una terminal.

**Qué no toca nunca**: `HKLM`, `Program Files`, servicios, el PATH de la máquina, y
`~\.claude\.credentials.json`, que está justo al lado del `settings.json` que sí lee.

Si no tienes Python, el instalador lo pone con `winget` en ámbito de usuario, que tampoco
pide contraseña. No hay firewall de por medio: la app no abre ni un socket. Y no hace
falta excluir nada del antivirus ni firmar nada, porque no se instala ningún ejecutable
propio.

Lo único que puede pedirte Windows es **desbloquear los archivos** si te llegaron dentro
de un `.zip` descargado: todo lo que sale de una descarga viene con la Marca de la Web y
PowerShell se niega a ejecutarlo. Es el equivalente exacto del `xattr -dr
com.apple.quarantine` de macOS que se explica más abajo:

```powershell
Unblock-File -Path .\*.ps1
```

Detalle en [`windows/README.md`](windows/README.md).

---

## Opción A — compilarla (recomendada)

Al compilarla en tu propia máquina no hay cuarentena ni Gatekeeper de por medio.

```bash
git clone <este-repo> && cd ClaudePet
./build.sh
open ClaudePet.app
```

Requisito único: las Command Line Tools de Apple (gratis, sin Xcode entero). Si faltan,
`build.sh` te lo dice y se instalan con `xcode-select --install`.

---

## Opción B — recibir el `.zip`

`./package.sh` genera un `ClaudePet-1.0.zip` de ~200 KB con la app, este documento y un
instalador. Para quien lo recibe es un solo paso:

```bash
bash ~/Downloads/install.sh
```

Copia la app a `/Applications`, le quita la cuarentena, la abre y pregunta si quiere que
arranque al iniciar sesión. (Con `CLAUDEPET_DEST` se instala en otro sitio, p. ej.
`~/Applications`.)

**Hay que usar el instalador, no el doble clic.** La app va firmada *ad-hoc*, sin cuenta
de desarrollador de Apple: al descargarla queda con el atributo de cuarentena y el
diálogo que sale no ofrece «Abrir», solo «Mover a la papelera». El instalador lo
resuelve con `xattr -dr com.apple.quarantine`, que es justo lo que el doble clic no
puede hacer.

## Que muestre tu cuota

Recién instalada, Clawd puede aparecer con **`0/0 %`**: todavía no tiene de dónde leer.
Lee de dos sitios y al principio los dos pueden estar vacíos:

- `~/.claude.json` → `cachedUsageUtilization`: lo escribe Claude Code solo, y puede tardar.
- `~/.claude/pet-usage.json`: lo escribe el hook de `statusLine`, que **no se instala con
  la app**.

Instala el hook (gratis, sin red ni tokens):

```bash
./install-statusline.sh   # engancha el hook en ~/.claude/settings.json (hace backup)
```

> **Reinicia Claude Code después.** El `statusLine` se carga al arrancar, así que hasta
> que no reinicies no empieza a escribir los datos.

Para ver qué está leyendo, sin tocar nada:

```bash
ClaudePet.app/Contents/MacOS/ClaudePet --dump
```

> Si instalaste desde el `.zip`, `install.sh` ya te ofrece instalar el hook al final.

### Diagnóstico en planes Team y Enterprise

Esos planes se miden en dinero y no están probados con datos reales. Si algo no cuadra,
este comando vuelca el bloque de cuota quitando todo lo que identifica a la cuenta
(UUID, correos, tokens, ids):

```bash
ClaudePet.app/Contents/MacOS/ClaudePet --dump-raw
```

Salen unos 3 KB. Repasa la salida antes de mandarla: lleva tus porcentajes de uso y, si
el plan va por dinero, los importes.

---

## Desinstalar

```bash
./start-at-login.sh --off             # quitar del arranque
rm -rf /Applications/ClaudePet.app    # borrar la app
```

No deja nada más: sus ajustes viven en `~/Library/Preferences/com.mario.claudepet.plist`
y nunca escribe fuera de ahí. Si además instalaste el hook de statusLine,
`./uninstall-statusline.sh` lo revierte.

En Ubuntu es `./install-linux.sh --user off`, y en Windows
`powershell -ExecutionPolicy Bypass -File .\install-windows.ps1 off`. Los dos preguntan
si quitar también el hook y los dos conservan tus ajustes, por si vuelves.
