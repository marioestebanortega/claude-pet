---
description: Instala Claude Pet (macOS, Ubuntu o Windows, según el sistema) y configura el hook de statusLine si falta
---

Instala **Claude Pet** de principio a fin. Trabaja desde la raíz del repo.

## 0. Detectar el sistema

Mira la línea `Platform` del contexto de Claude Code: `darwin` → macOS, `linux` → Linux,
`win32` → Windows. Si no está disponible, `uname -s` funciona en bash/zsh; si `uname` no
existe, estás en PowerShell → Windows.

## 1a. macOS

1. Comprueba el compilador: `xcrun --find swiftc`. Si falla → `xcode-select --install` y espera.
2. Compila e instala: `./build.sh && open ClaudePet.app`
3. Verifica: `pgrep -x ClaudePet`

## 1b. Ubuntu/Linux

1. Instala: `./install-linux.sh --user` (sin sudo; genera el `.deb` y lo instala con apt)
2. Sin instalar: `cd linux && python3 -m claudepet &`

## 1c. Windows

**Instalar** (sin administrador):
```powershell
powershell -ExecutionPolicy Bypass -File .\install-windows.ps1
```
El `-ExecutionPolicy Bypass` es obligatorio: Windows 11 tiene la política en `Restricted`
por defecto. Si no hay Python, el instalador lo descarga con `winget --scope user`.

**Correr sin instalar** (para desarrollo o prueba rápida):
```powershell
cd windows
python -X utf8 -m claudepet
```

**Construir el zip portable**:
```powershell
python windows\build-zip.py   # genera dist\ClaudePet-1.0-windows.zip
```

**Verificar**: `claudepet --dump` (o `python -X utf8 -m claudepet --dump` desde `windows\`)

> Windows 11 esconde los iconos nuevos de la bandeja detrás de la flecha `^`. Si no ves
> a Clawd ahí, ábrela y arrástralo fuera. La mascota del escritorio sí se ve siempre.

## 2. Hook de statusLine — el paso que suele faltar

Sin el hook la mascota suele quedarse en `0/0 %`. Comprueba `~/.claude/settings.json`:
si `statusLine.command` ya contiene `statusline-pet.py` → no toques nada. Si no:

| Sistema | Comando |
|---|---|
| macOS | `./install-statusline.sh` |
| Linux (instalado) | `claudepet --install-statusline` |
| Linux (fuente) | `cd linux && python3 -m claudepet --install-statusline` |
| Windows (instalado) | `claudepet --install-statusline` |
| Windows (fuente) | `cd windows; python -X utf8 -m claudepet --install-statusline` |

**Comprueba también las settings del proyecto**: `.claude/settings.local.json` y
`.claude/settings.json` del directorio actual ganan sobre `~/.claude/settings.json`.
Si hay un `statusLine` ajeno ahí, el hook no se ejecuta aunque esté instalado. `--dump`
lo detecta y lo dice.

## 3. Reiniciar Claude Code

El `statusLine` se carga al arrancar. Sin reinicio el hook no escribe datos y la mascota
sigue en `0/0 %`.

## 4. Verificar y resumir

```
macOS:   ClaudePet.app/Contents/MacOS/ClaudePet --dump
Linux:   claudepet --dump  (o python3 -m claudepet --dump)
Windows: claudepet --dump  (o python -X utf8 -m claudepet --dump desde windows\)
```

Resume en 4-5 líneas: qué instalaste, si el hook ya estaba o lo pusiste tú, el aviso de
reiniciar Claude Code, y cómo desinstalar (`install-windows.ps1 off`, `install-linux.sh
--user off`, o borrar `ClaudePet.app` + `./uninstall-statusline.sh`).
