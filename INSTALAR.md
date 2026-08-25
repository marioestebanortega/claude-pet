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

## En macOS — compilar e instalar

```bash
git clone <este-repo> && cd ClaudePet
./build.sh && open ClaudePet.app
```

Requisito único: Command Line Tools (`xcode-select --install`). Compilar en local evita
Gatekeeper por completo; no hace falta tocar `xattr`.

Para empaquetar y compartir: `./package.sh` genera `ClaudePet-1.0.zip` con un
`install.sh` que quita la cuarentena, copia a `/Applications` y ofrece instalar el hook.

---

## Que muestre tu cuota

Recién instalada puede aparecer `0/0 %`. Instala el hook de `statusLine`:

```bash
# macOS / Linux
./install-statusline.sh

# Windows
claudepet --install-statusline
# o desde el fuente:
cd windows && python -X utf8 -m claudepet --install-statusline
```

**Reinicia Claude Code después.** El hook empieza a escribir datos solo al arrancar.

Para ver qué está leyendo:
```bash
ClaudePet.app/Contents/MacOS/ClaudePet --dump   # macOS
claudepet --dump                                 # Linux / Windows (instalado)
python -X utf8 -m claudepet --dump               # Windows (fuente), desde windows\
```

---

## Desinstalar

| Sistema | Comando |
|---|---|
| macOS | `./start-at-login.sh --off && rm -rf /Applications/ClaudePet.app` |
| Linux | `./install-linux.sh --user off` |
| Windows | `powershell -ExecutionPolicy Bypass -File .\install-windows.ps1 off` |

Para quitar solo el hook: `./uninstall-statusline.sh` (macOS/Linux) o
`claudepet --install-statusline off` (Windows).
