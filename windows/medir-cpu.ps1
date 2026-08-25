# Mide lo que cuesta Claude Pet en esta máquina.
#
# Hermano de linux/medir-cpu.sh. Allí se lee /proc/<pid>/stat directamente en vez
# de fiarse del %CPU que enseña `top`; aquí el equivalente honrado es
# TotalProcessorTime del propio proceso, que es tiempo de CPU acumulado (usuario
# + kernel) y no una media móvil inventada por nadie.
#
#   powershell -ExecutionPolicy Bypass -File .\windows\medir-cpu.ps1
#   powershell -ExecutionPolicy Bypass -File .\windows\medir-cpu.ps1 -Segundos 60
#
# Dos cifras salen de aquí, y las dos van al README:
#   1. lo que cuesta una consulta de /usage (arrancar el CLI entero)
#   2. lo que cuesta la mascota animada mientras está en pantalla

[CmdletBinding()]
param([int] $Segundos = 30, [int] $Consultas = 3)

$ErrorActionPreference = 'Stop'

function Buscar-Claude {
    foreach ($p in "$env:USERPROFILE\.local\bin\claude.exe",
                   "$env:APPDATA\npm\claude.cmd",
                   "$env:LOCALAPPDATA\Programs\claude\claude.exe") {
        if (Test-Path $p) { return $p }
    }
    $c = Get-Command claude -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
    return $null
}

Write-Host ''
Write-Host '1. Coste de una consulta de /usage'
$claude = Buscar-Claude
if (-not $claude) {
    Write-Warning '  No encuentro `claude`; me salto esta parte.'
} else {
    Write-Host "   $claude"
    $cpu = @(); $ram = @(); $reloj = @()
    for ($i = 1; $i -le $Consultas; $i++) {
        $t0 = Get-Date
        $p = Start-Process -FilePath $claude -ArgumentList '-p', '/usage' `
                           -PassThru -NoNewWindow -RedirectStandardOutput ([IO.Path]::GetTempFileName())
        # Hay que sondear mientras vive: cuando el proceso muere, Windows ya no
        # deja consultarle ni el pico de memoria ni el tiempo de CPU. Guardar la
        # última lectura buena es lo único que funciona siempre; leerlo después
        # de `WaitForExit` da vacío según cuándo lo recoja el sistema.
        $pico = 0; $tcpu = 0
        while (-not $p.HasExited) {
            try {
                $p.Refresh()
                $pico = [Math]::Max($pico, $p.PeakWorkingSet64)
                $tcpu = [Math]::Max($tcpu, $p.TotalProcessorTime.TotalSeconds)
            } catch { }
            Start-Sleep -Milliseconds 50
        }
        $p.WaitForExit()
        try { $tcpu = [Math]::Max($tcpu, $p.TotalProcessorTime.TotalSeconds) } catch { }
        $reloj += ((Get-Date) - $t0).TotalSeconds
        $cpu += $tcpu
        $ram += $pico / 1MB
        Write-Host ("   {0}: {1:N2} s de reloj · {2:N2} s de CPU · {3:N0} MB de pico" -f `
                    $i, $reloj[-1], $cpu[-1], $ram[-1])
    }
    $media = ($cpu | Measure-Object -Average).Average
    Write-Host ("   media: {0:N2} s de CPU por consulta" -f $media)
    foreach ($cada in 60, 120, 300, 900) {
        Write-Host ("     una cada {0,3} s → {1:N1} % de un núcleo" -f `
                    $cada, ($media / $cada * 100))
    }
    Write-Host '   (esa media es la que va en AUTO_FORCE_CPU_SECONDS, en hub.py)'
}

Write-Host ''
Write-Host "2. Coste de la mascota, midiendo $Segundos s"
$pet = Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" `
       -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'claudepet' }
if (-not $pet) {
    Write-Warning '  Claude Pet no está corriendo. Ábrelo y vuelve a lanzar esto.'
    Write-Host '  (con la mascota escondida el coste baja a casi cero: es el dibujo lo que gasta)'
    exit 0
}
$proc = Get-Process -Id $pet.ProcessId
$antes = $proc.TotalProcessorTime
Start-Sleep -Seconds $Segundos
$proc.Refresh()
$gasto = ($proc.TotalProcessorTime - $antes).TotalSeconds
Write-Host ("   {0:N2} s de CPU en {1} s → {2:N1} % de un núcleo" -f `
            $gasto, $Segundos, ($gasto / $Segundos * 100))
Write-Host ("   memoria: {0:N0} MB" -f ($proc.WorkingSet64 / 1MB))
Write-Host ''
Write-Host '   Para comparar, escóndela desde la bandeja («Mascota en el escritorio»)'
Write-Host '   y repite: lo que gasta es el dibujo, no el sondeo de los archivos.'
