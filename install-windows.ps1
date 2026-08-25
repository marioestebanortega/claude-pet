# Instala Claude Pet en Windows, solo para tu usuario.
#
# Es el hermano de install-linux.sh --user, y con la misma promesa: NUNCA hace
# falta administrador. Todo lo que escribe está en tu perfil
# (%LOCALAPPDATA%, %APPDATA%, el menú Inicio y HKCU\Environment) y de
# ~\.claude.json solo lee.
#
#   powershell -ExecutionPolicy Bypass -File .\install-windows.ps1
#   powershell -ExecutionPolicy Bypass -File .\install-windows.ps1 off
#
# El -ExecutionPolicy Bypass no es adorno: la política por defecto en Windows 11
# es Restricted, que no deja ejecutar NINGÚN script, ni siquiera uno local.

[CmdletBinding()]
param([ValidateSet('', 'off')] [string] $Accion = '')

$ErrorActionPreference = 'Stop'

$Repo = Split-Path -Parent $MyInvocation.MyCommand.Path
# El paquete está en `windows\claudepet` cuando esto se lanza desde el repo, y
# en `claudepet` a secas cuando se lanza desde el .zip portable, donde todo va
# junto en la raíz. El hook y este mismo script están en la raíz en los dos.
$Fuente = Join-Path $Repo 'windows\claudepet'
if (-not (Test-Path $Fuente)) { $Fuente = Join-Path $Repo 'claudepet' }
$App = Join-Path $env:LOCALAPPDATA 'Programs\ClaudePet'
$Programs = [Environment]::GetFolderPath('Programs')
$Startup = [Environment]::GetFolderPath('Startup')
$LnkInicio = Join-Path $Programs 'Claude Pet.lnk'
$LnkArranque = Join-Path $Startup 'Claude Pet.lnk'

function Say([string] $t) { Write-Host $t }
function Paso([string] $t) { Write-Host "  $t" }

function Ask([string] $pregunta, [string] $porDefecto = 'S') {
    <#
      Read-Host lanza una excepción si no hay nadie al otro lado (una tubería que
      ya se agotó, una sesión sin consola). Con $ErrorActionPreference = 'Stop'
      eso abortaría la instalación entera justo al final, cuando ya está todo
      copiado. Sin respuesta, se toma la de por defecto.
    #>
    try { $r = Read-Host $pregunta } catch { return $porDefecto }
    if ([string]::IsNullOrWhiteSpace($r)) { return $porDefecto }
    return $r
}

# ─────────────────────────────────────────────────────────────
# Python
# ─────────────────────────────────────────────────────────────
function Test-PythonReal {
    <#
      Devuelve la versión ("3.13") si $exe es un Python de verdad, o $null.

      El caso difícil de Windows no es que falte Python: es que PARECE que está.
      Windows deja en %LOCALAPPDATA%\Microsoft\WindowsApps un python.exe de cero
      bytes que es un alias de ejecución de la Microsoft Store — existe, sale en
      el PATH, Get-Command lo encuentra, y al llamarlo abre la tienda y falla.
      Se detecta por lo que es (cero bytes + punto de reanálisis) y NO
      ejecutándolo, porque ejecutarlo le abriría la Store al usuario en la cara.
    #>
    param([string] $exe)
    if (-not $exe) { return $null }
    if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { return $null }
    $item = Get-Item -LiteralPath $exe -Force
    if ($item.Length -eq 0) { return $null }
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { return $null }
    try { $v = & $exe -c "import sys;sys.stdout.write('%d.%d' % sys.version_info[:2])" }
    catch { return $null }
    if ($LASTEXITCODE -ne 0 -or -not $v) { return $null }
    $n = $v.Split('.')
    if ([int]$n[0] -lt 3 -or ([int]$n[0] -eq 3 -and [int]$n[1] -lt 9)) { return $null }
    return $v
}

function Find-Python {
    $c = New-Object System.Collections.Generic.List[string]
    # Salida de emergencia, para forzar un intérprete concreto.
    if ($env:CLAUDEPET_PYTHON) { $c.Add($env:CLAUDEPET_PYTHON) }
    # El registro (PEP 514) es la forma documentada de encontrar los Python
    # instalados. Va antes que el PATH porque el PATH miente (ver el alias).
    foreach ($hive in 'HKCU:\Software\Python', 'HKLM:\SOFTWARE\Python') {
        Get-ChildItem "$hive\*\*\InstallPath" -ErrorAction SilentlyContinue | ForEach-Object {
            $p = $_.GetValue('ExecutablePath')
            if (-not $p) { $p = Join-Path $_.GetValue('') 'python.exe' }
            if ($p) { $c.Add($p) }
        }
    }
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        $s = & $py.Source -3 -c "import sys;sys.stdout.write(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $s) { $c.Add($s) }
    }
    foreach ($g in "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe",
                   "$env:ProgramFiles\Python3*\python.exe") {
        Get-ChildItem $g -ErrorAction SilentlyContinue | ForEach-Object { $c.Add($_.FullName) }
    }
    Get-Command python.exe -All -ErrorAction SilentlyContinue |
        ForEach-Object { $c.Add($_.Source) }

    foreach ($exe in ($c | Select-Object -Unique)) {
        $v = Test-PythonReal $exe
        if ($v) { return [pscustomobject]@{ Exe = $exe; Version = $v } }
    }
    return $null
}

function Install-Python {
    Paso 'No hay Python en esta máquina. Lo instalo con winget.'
    Paso 'Se instala SOLO PARA TI (--scope user): no pide contraseña de'
    Paso 'administrador ni escribe nada fuera de tu perfil.'
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw ("No hay winget. Instala Python 3 desde " +
               "https://www.python.org/downloads/windows/ y vuelve a lanzar esto.")
    }
    # `-s winget` no es adorno: en una máquina recién estrenada winget se planta
    # con el código 70 pidiendo aceptar los términos de la fuente `msstore`, que
    # aquí no se usa para nada.
    $a = @('install', '-e', '--id', 'Python.Python.3.13', '-s', 'winget',
           '--scope', 'user', '--silent', '--disable-interactivity',
           '--accept-package-agreements', '--accept-source-agreements')
    & winget @a
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "winget devolvió $LASTEXITCODE con --scope user; reintento sin él."
        & winget @($a | Where-Object { $_ -notin @('--scope', 'user') })
        if ($LASTEXITCODE -ne 0) { throw "No pude instalar Python (winget: $LASTEXITCODE)." }
    }
    # El instalador acaba de tocar el PATH del registro, pero ESTE proceso lleva
    # todavía la copia vieja en memoria: hay que releerlo o la búsqueda siguiente
    # volvería a no encontrar nada.
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                [Environment]::GetEnvironmentVariable('Path', 'User')
}

# ─────────────────────────────────────────────────────────────
# Accesos directos y PATH
# ─────────────────────────────────────────────────────────────
function New-Lnk {
    <#
      Un .lnk es el equivalente del .desktop de Linux: es lo que hace que la app
      salga en el menú Inicio con su nombre y su icono. Se escribe con el COM de
      WScript.Shell, que es la única forma sin dependencias de generar uno (un
      .url no admite argumentos ni icono, y escribir el formato binario a mano
      son trescientas líneas de `struct` para nada).

      El icono NO puede ser un PNG: el shell de Windows solo acepta .ico, .exe
      o .dll. De ahí el claudepet.ico que genera este instalador.
    #>
    param([string] $Path, [string] $Target, [string] $Arguments,
          [string] $WorkDir, [string] $Icon, [string] $Description)
    $ws = New-Object -ComObject WScript.Shell
    try {
        $l = $ws.CreateShortcut($Path)
        $l.TargetPath = $Target
        $l.Arguments = $Arguments
        $l.WorkingDirectory = $WorkDir
        if ($Icon) { $l.IconLocation = "$Icon,0" }
        $l.Description = $Description
        $l.Save()
    } finally {
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($ws)
    }
}

function Get-RawUserPath {
    (Get-Item 'HKCU:\Environment').GetValue(
        'Path', '', [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
}

function Set-RawUserPath([string] $value) {
    <#
      Añadir al PATH del usuario tiene una trampa fea en Windows: el valor del
      registro es REG_EXPAND_SZ y suele contener, literalmente,
      "%USERPROFILE%\AppData\Local\Microsoft\WindowsApps;...". Tanto `setx` como
      [Environment]::SetEnvironmentVariable leen el valor YA EXPANDIDO y lo
      reescriben como REG_SZ: el %USERPROFILE% se congela y el PATH deja de ser
      portable. (`setx`, además, trunca a 1024 caracteres.) Por eso se lee sin
      expandir y se reescribe con el mismo tipo.
    #>
    New-ItemProperty -Path 'HKCU:\Environment' -Name Path -Value $value `
                     -PropertyType ExpandString -Force | Out-Null
    # Avisar al shell de que el entorno cambió, para que las terminales nuevas lo
    # cojan sin cerrar sesión. Es el `update-desktop-database` de aquí.
    if (-not ('Win32.Env' -as [type])) {
        Add-Type -Namespace Win32 -Name Env -MemberDefinition @'
[DllImport("user32.dll", SetLastError=true, CharSet=CharSet.Auto)]
public static extern IntPtr SendMessageTimeout(IntPtr hWnd, uint Msg, UIntPtr wParam,
    string lParam, uint fuFlags, uint uTimeout, out UIntPtr lpdwResult);
'@
    }
    $r = [UIntPtr]::Zero
    [void][Win32.Env]::SendMessageTimeout([IntPtr]0xFFFF, 0x1A, [UIntPtr]::Zero,
                                          'Environment', 2, 5000, [ref]$r)
}

function Add-UserPath([string] $dir) {
    $raw = Get-RawUserPath
    $parts = $raw -split ';' | Where-Object { $_ -ne '' }
    if ($parts -contains $dir) { return }
    Set-RawUserPath ((@($parts) + $dir) -join ';')
}

function Remove-UserPath([string] $dir) {
    $raw = Get-RawUserPath
    $parts = $raw -split ';' | Where-Object { $_ -ne '' -and $_ -ne $dir }
    Set-RawUserPath ($parts -join ';')
}

function Stop-ClaudePet {
    # Equivalente del `pkill -f "^python3 -m claudepet"` de Linux. Aquí no hay
    # pkill, y Stop-Process solo casa por nombre —que es "pythonw.exe" y puede
    # ser de cualquiera—, así que hay que mirar la línea de comandos. Win32_Process
    # deja leerla para los procesos de uno mismo sin ser administrador.
    Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" `
        -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match 'claudepet' } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}

# ─────────────────────────────────────────────────────────────
# Desinstalar
# ─────────────────────────────────────────────────────────────
if ($Accion -eq 'off') {
    Say ''
    Say '🦞 Desinstalando Claude Pet'
    Stop-ClaudePet

    # El hook se quita ANTES de borrar la app: después ya no habría comando.
    if (Test-Path (Join-Path $App 'claudepet.cmd')) {
        $r = Ask "  ¿Quito también el hook de statusLine? [S/n]"
        if ($r -notmatch '^[nN]') { & (Join-Path $App 'claudepet.cmd') --install-statusline off }
    }

    foreach ($p in $LnkInicio, $LnkArranque) {
        if (Test-Path $p) { Remove-Item -Force $p; Paso "🗑  $p" }
    }
    if (Test-Path $App) { Remove-Item -Recurse -Force $App; Paso "🗑  $App" }
    Remove-UserPath $App

    Say ''
    Say '  ✅ Desinstalado.'
    Say '     Tus ajustes siguen en %APPDATA%\ClaudePet\ por si vuelves.'
    Say '     Para borrarlos también: Remove-Item -Recurse $env:APPDATA\ClaudePet'
    exit 0
}

# ─────────────────────────────────────────────────────────────
# Instalar
# ─────────────────────────────────────────────────────────────
Say ''
Say '🦞 Claude Pet para Windows'
Say '   Instalación de usuario: sin administrador, todo dentro de tu perfil.'
Say ''

$id = [Security.Principal.WindowsIdentity]::GetCurrent()
if ((New-Object Security.Principal.WindowsPrincipal $id).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Warning ("Estás ejecutando esto como administrador. Se instalaría en el " +
                   "perfil del ADMINISTRADOR, no en el tuyo. Ábrelo en una " +
                   "PowerShell normal.")
    $r = Ask "  ¿Sigo de todas formas? [s/N]" "N"
    if ($r -notmatch '^[sS]') { exit 1 }
}

Say '1. Buscando Python…'
$py = Find-Python
if (-not $py) {
    Install-Python
    $py = Find-Python
    if (-not $py) { throw 'Sigo sin encontrar Python después de instalarlo.' }
}
Paso "✅ Python $($py.Version) en $($py.Exe)"

# La app corre sin consola con pythonw.exe; el hook y --dump necesitan python.exe
# (pythonw no tiene stdout y `print` se vuelve un no-op silencioso).
$pythonw = Join-Path (Split-Path $py.Exe) 'pythonw.exe'
if (-not (Test-Path $pythonw)) { $pythonw = $py.Exe }

Say '2. Copiando la aplicación…'
Stop-ClaudePet                                  # no copiar encima de algo en marcha
New-Item -ItemType Directory -Force -Path (Join-Path $App 'claudepet') | Out-Null
Copy-Item (Join-Path $Fuente '*.py') (Join-Path $App 'claudepet') -Force
# El hook, AL LADO del paquete: es donde lo busca `_hook_source()`, igual que el
# .deb lo deja junto a claudepet/ en /usr/lib.
Copy-Item (Join-Path $Repo 'statusline-pet.py') $App -Force
Paso "✅ $App"

Say '3. Generando el icono…'
$env:PYTHONPATH = $App
& $py.Exe -X utf8 -m claudepet --ico (Join-Path $App 'claudepet.ico') | Out-Null
Paso '✅ claudepet.ico'

Say '4. Lanzadores y accesos directos…'
# El de consola, para --dump y --install-statusline, que SÍ imprimen.
#
# Dos detalles que lo rompen en silencio si se descuidan: cmd.exe exige saltos
# CRLF (con saltos de Unix parte las lineas por donde no es y da errores del
# tipo «"em" no se reconoce»), y el contenido va en ASCII puro, sin acentos,
# porque un .bat se interpreta con la pagina de codigos OEM de la maquina y no
# hay una sola que valga en todas.
$cmd = @"
@echo off
rem Lanzador de Claude Pet.
rem Usa python.exe y no pythonw.exe: este es el que se llama desde una terminal,
rem y esos comandos escriben por pantalla (pythonw no tiene stdout).
rem -X utf8 porque la salida lleva emojis y la pagina de codigos local no sabe
rem escribirlos.
setlocal
set "PYTHONPATH=%~dp0;%PYTHONPATH%"
"$($py.Exe)" -X utf8 -m claudepet %*
exit /b %ERRORLEVEL%
"@
$cmd = $cmd -replace "`r?`n", "`r`n"
[IO.File]::WriteAllText((Join-Path $App 'claudepet.cmd'), $cmd,
                        [Text.Encoding]::ASCII)

# El gráfico, sin ventana de consola.
$pyw = @'
"""Lanzador sin ventana de consola.

Mete su propio directorio en `sys.path` en vez de fiarse de PYTHONPATH o del
directorio de trabajo: un acceso directo puede traer cualquiera de los dos, y el
del arranque automático empieza con el que le dé la gana al shell.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from claudepet.__main__ import main

raise SystemExit(main())
'@
# UTF-8 sin BOM: el archivo lleva acentos en el docstring y Python 3 da por
# hecho UTF-8 en el fuente, así que el BOM solo sobra.
[IO.File]::WriteAllText((Join-Path $App 'claudepet.pyw'), $pyw,
                        (New-Object Text.UTF8Encoding $false))

$lnkArgs = '-X utf8 "{0}"' -f (Join-Path $App 'claudepet.pyw')
$icono = Join-Path $App 'claudepet.ico'
try {
    New-Lnk -Path $LnkInicio -Target $pythonw -Arguments $lnkArgs -WorkDir $App `
            -Icon $icono -Description 'Vigila tu consumo de Claude Code'
    # La plantilla que copia `--autostart`: así ese comando no necesita montar el
    # COM de IShellLink desde Python.
    New-Lnk -Path (Join-Path $App 'claudepet-autostart.lnk') -Target $pythonw `
            -Arguments $lnkArgs -WorkDir $App -Icon $icono `
            -Description 'Vigila tu consumo de Claude Code'
    Paso '✅ Claude Pet en el menú Inicio'
} catch {
    Write-Warning "No pude crear los accesos directos ($_). La app funciona igual desde claudepet.cmd."
}

Add-UserPath $App
Paso '✅ claudepet disponible en las terminales nuevas'

Say '5. Comprobando que lee tus datos…'
& (Join-Path $App 'claudepet.cmd') --dump
Say ''

$r = Ask "¿Instalo el hook de statusLine? Es lo que da el dato fresco. [S/n]"
if ($r -notmatch '^[nN]') {
    & (Join-Path $App 'claudepet.cmd') --install-statusline
}

$r = Ask "¿Que arranque al iniciar sesión? [S/n]"
if ($r -notmatch '^[nN]') {
    & (Join-Path $App 'claudepet.cmd') --autostart
}

Say ''
Say '  ✅ Listo. Arráncalo desde el menú Inicio, o con: claudepet'
Say ''
Say '  ⚠️  Windows 11 esconde los iconos nuevos de la bandeja detrás de la'
Say '      flecha ^ de la esquina. Si no ves a Clawd ahí, ábrela y arrástralo'
Say '      fuera. La mascota del escritorio sale igualmente.'
Say ''
Say '  Para quitarlo: powershell -ExecutionPolicy Bypass -File .\install-windows.ps1 off'
