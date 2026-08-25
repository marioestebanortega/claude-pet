# Claude Pet para Windows

Icono de bandeja y mascota flotante que vigilan tu consumo de Claude Code. Mismo motor
que las versiones de macOS y Ubuntu, reescrito en Python sobre Win32: la app de macOS no
se puede portar (SwiftUI, AppKit y compañía son exclusivos de Darwin) y la de Linux
tampoco (GTK, AppIndicator y Cairo no están aquí).

**Sin dependencias de `pip`.** Todo sale de la biblioteca estándar y de `ctypes`: el
icono de la bandeja es `Shell_NotifyIcon`, la mascota una ventana en capas dibujada por
un rasterizador propio, y el `.ico` y el PNG se escriben a mano con `struct` y `zlib`.
Es la misma decisión que toma `linux/build-deb.py` al escribir el formato `ar` en vez de
llamar a `dpkg-deb`.

## Instalar

```powershell
powershell -ExecutionPolicy Bypass -File .\install-windows.ps1
powershell -ExecutionPolicy Bypass -File .\install-windows.ps1 off
```

El `-ExecutionPolicy Bypass` **no es opcional**: el valor por defecto en Windows 11 es
`Restricted`, que no deja ejecutar ningún script, ni siquiera uno local tuyo.

**No hace falta administrador, en ningún momento.** Todo lo que se escribe está en tu
perfil:

| Dónde | Qué |
|---|---|
| `%LOCALAPPDATA%\Programs\ClaudePet\` | la app, el hook, el icono y los lanzadores |
| `%APPDATA%\ClaudePet\state.json` | los ajustes y la posición de la mascota |
| Menú Inicio · Inicio automático | los dos accesos directos |
| `HKCU\Environment` → `Path` | para poder escribir `claudepet` en una terminal |

De `~\.claude.json` **solo lee**. Nunca toca `HKLM`, `Program Files`, servicios, el PATH
de la máquina ni `~\.claude\.credentials.json`.

> No lo ejecutes desde una PowerShell de administrador: instalaría en el perfil del
> administrador y no en el tuyo. El instalador avisa si lo detecta.

### Si no tienes Python

El instalador lo pone él:

```powershell
winget install -e --id Python.Python.3.13 -s winget --scope user
```

`--scope user` es lo que mantiene la promesa de «sin administrador»: el manifiesto de
Python publica instaladores de usuario para x86, x64 y ARM64. Y `-s winget` tampoco
sobra: sin él, en una máquina recién estrenada winget se planta con el código 70 pidiendo
aceptar los términos de la fuente `msstore`, que aquí no se usa para nada.

**Ojo con la trampa del alias de la Store.** En `%LOCALAPPDATA%\Microsoft\WindowsApps`
hay un `python.exe` de **cero bytes** que es un alias de ejecución de la Microsoft Store.
Existe, sale en el PATH, `where python` lo encuentra… y al ejecutarlo abre la tienda y
falla. El instalador lo descarta por lo que es (cero bytes y punto de reanálisis) y sin
ejecutarlo, que sería abrirte la Store en la cara.

## El hook de `statusLine` (recomendado)

Hay dos fuentes locales y la app las fusiona, pero solo una se refresca de verdad:

| Fuente | Cada cuánto | Qué trae |
|---|---|---|
| `~\.claude.json` | muy de tarde en tarde (medido: una vez en 22 min) | todas las dimensiones, gasto y créditos de empresa |
| `~\.claude\pet-usage.json` | cada 10 s, lo escribe el hook | solo sesión y semana, pero al día |

```powershell
claudepet --install-statusline        # off para quitarlo
```

Copia el hook a `~\.claude\statusline-pet.py` y añade la entrada a
`~\.claude\settings.json`, con copia de seguridad antes y avisando si ya tenías otro
`statusLine` (en ese caso `off` no te lo borra, lo restaura). **Reinicia Claude Code
después.**

El comando que se instala tiene tres detalles que no son manías:

```
"C:\...\python.exe" -X utf8 "C:\Users\tú\.claude\statusline-pet.py"
```

- **La ruta completa del intérprete**, no `python`: el `python` del PATH puede ser el
  alias de la Store, y aun con Python instalado el orden del PATH no está garantizado.
- **`python.exe` y no `pythonw.exe`**: `pythonw` no tiene stdout —`sys.stdout` es `None` y
  `print` se convierte en un no-op silencioso—, así que la línea de estado saldría vacía
  para siempre y sin decir por qué.
- **`-X utf8`**: el hook imprime emojis, y sin esto Python codifica su salida con la
  página de códigos local (cp1252 en España), que no sabe escribir 🐱. El hook reventaría
  en cada pasada y el traceback saldría en la barra de estado de Claude Code.

Si tienes varias sesiones de Claude Code abiertas, todas escriben el mismo
`pet-usage.json`; el hook funde las cifras en vez de sobrescribirlas y la app descarta las
ventanas ya vencidas, así que se ve un solo número coherente. El candado que lo permite es
`msvcrt.locking` en vez del `fcntl.flock` de POSIX, que en Windows no existe; el archivo
del hook es el mismo en las tres plataformas y elige uno u otro al importarse.

## Con Claude Code cerrado

El hook solo corre mientras hay una sesión abierta, así que al cerrar Claude Code la cifra
se congela. No es un fallo —con Claude Code cerrado tu cuota tampoco se mueve—, pero la
ventana de 5 h y la de 7 días siguen avanzando y el dato envejece.

Por eso Clawd pide `/usage` él solo cuando hace falta. El interruptor está en la bandeja y
en el clic derecho de la mascota, en «Consultar /usage sola (no gasta tokens)», y viene
encendido:

| Plan | Cuándo dispara |
|---|---|
| Pro/Max | solo si el dato pasa de 15 min (o las cifras llevan ese rato clavadas) |
| Team/Enterprise | cada vez que toca el temporizador (esos planes no publican `rate_limits`) |

`/usage` no gasta tokens; lo que cuesta es arrancar el CLI: ~1,43 s de CPU y ~410 MB de
pico por consulta en Windows 11 ARM64 (más que Linux por el coste de crear procesos). El
menú muestra el porcentaje equivalente debajo del interruptor. La mascota sola sale casi
gratis: 0,03 s de CPU en 30 s y ~26 MB de RAM.

Los ajustes viven en `%APPDATA%\ClaudePet\state.json`.

## Sin instalar nada

```powershell
cd windows
python -X utf8 -m claudepet --dump
```

`--dump` no toca la interfaz, así que funciona aunque algo de Win32 falle. Es lo primero
que hay que probar en una máquina nueva: si muestra tus cifras, el problema es solo de
interfaz.

```
  --dump              muestra el consumo y sale (no toca la interfaz)
  --icon [ruta]       escribe el PNG de Clawd  [--night] [--tint]
  --ico [ruta]        escribe el .ico del acceso directo  [--night]
  --autostart [off]   arrancar al iniciar sesión
  --install-statusline [off]  pone el hook que da el dato fresco
  --pet               solo la mascota flotante, sin bandeja
  --no-pet            solo la bandeja, sin mascota
  --pet-png [ruta]    vuelca la mascota a PNG  [--night] [--scale=N]
  sin argumentos      bandeja + mascota, según el estado guardado
```

## La bandeja

| Gesto | Qué hace |
|---|---|
| Clic izquierdo o derecho | abre el menú (los dos, como el applet de Linux) |
| Pasar el ratón | sesión, semana y antigüedad del dato |

El menú lleva las cifras de cada dimensión, la antigüedad del dato, «Mascota en el
escritorio», «Actualizar ahora», «Forzar (/usage)», el interruptor de la consulta
automática con su selector de intervalo, los avisos al cruzar 50/70/90 % y «Salir».

## La mascota flotante

Ventana sin marco y con **alfa real por píxel**, siempre por encima del escritorio: el
plato, los dos anillos (el exterior es la semana, el interior la sesión), Clawd dentro y
el badge con `sesión/semana %`.

| Gesto | Qué hace |
|---|---|
| Arrastrar | la mueve |
| Clic izquierdo | saluda, y de paso relee los archivos |
| Pasar el ratón | sesión, semana y antigüedad del dato, en un bocadillo |
| Clic derecho | ocultar, actualizar, forzar (`/usage`), consultar `/usage` sola, traer a esta pantalla, salir |

Se esconde y se saca desde la bandeja, con «Mascota en el escritorio». Lo visible y su
posición se guardan en `%APPDATA%\ClaudePet\state.json`.

Como los píxeles transparentes no son de la ventana, **los clics los atraviesan** sin
tener que calcular ninguna región; y como la ventana es `WS_EX_NOACTIVATE`, clicar a Clawd
no le roba el foco a lo que estuvieras escribiendo.

Aquí no hay nada parecido a la limitación de Wayland en Linux: la ventana siempre se puede
colocar, la posición se guarda y se restaura siempre, y «Traer a esta pantalla» significa
literalmente la pantalla donde está el cursor (en Linux va al monitor principal). Sí hay
que atender el cambio de DPI: arrastrarla de un monitor al 100 % a otro al 150 % rehace el
lienzo al tamaño nuevo.

## Diferencias con macOS y Linux

Tres, y conviene saberlas antes de pensar que algo va mal:

- **La bandeja de Windows no admite texto junto al icono.** En Linux el applet enseña
  `😺 25%` al lado, y en macOS lo mismo en la barra de menús; aquí eso no existe. La cifra
  de la sesión se pinta **dentro** del icono, con una fuente de píxeles de 3 × 5 dibujada
  a mano (a 16 px un dígito con antialiasing sale borroso, y uno de píxeles cae justo en
  la rejilla), y el color del número es el del humor. La línea completa va al tooltip.
- **Windows 11 esconde los iconos nuevos** detrás de la flecha `^` de la esquina. Si no
  ves a Clawd, ábrela y arrástralo fuera. Es la primera duda que tiene todo el mundo, y no
  es un fallo de la app. Abrirla dos veces no crea un segundo icono: la segunda instancia
  le pide a la primera que enseñe la mascota, que sí se ve.
- **La tipografía del badge.** macOS usa SF Rounded, Linux pide «Ubuntu» y aquí se pide
  Segoe UI Bold. Es la única diferencia visible en el dibujo.

## Construir el paquete

```powershell
python windows\build-zip.py
```

Genera `dist\ClaudePet-1.0-windows.zip` con el paquete, el hook, el icono y el
instalador. Funciona desde cualquier sistema, incluido un Mac, porque solo usa `zipfile`.
No hay MSI ni MSIX a propósito: los dos instalan por máquina (o sea, contraseña de
administrador) y MSIX además pide un certificado de firma.

Quien reciba el `.zip` tiene que desbloquearlo antes, porque Windows le pone la Marca de
la Web a todo lo que sale de una descarga:

```powershell
Unblock-File -Path .\*.ps1
```

Es el equivalente exacto del `xattr -dr com.apple.quarantine` que hace falta en macOS.

## Estructura

```
claudepet/
  usage.py   win32.py   loop.py   draw.py   icon.py
  menu.py    tray.py    pet.py    notify.py  app.py
  hub.py     runner.py  sprite.py state.py  __main__.py
build-zip.py    # genera el .zip portable
medir-cpu.ps1   # mide el coste de /usage y de la mascota
```

## Si algo falla

`--dump` te dice si el problema son los datos o la interfaz, y `--pet-png` (que dibuja
sin necesitar pantalla) si es el dibujo o la ventana. Compara su salida con
`docs/mascota-flotante.png`, que es la referencia exacta salida del código de macOS.

Y **arranca desde `claudepet.cmd`, no desde el acceso directo**, cuando algo no vaya: bajo
`pythonw.exe` no hay stderr y los errores se pierden sin dejar rastro. Es el equivalente
del «prueba `--dump` primero» del README de Linux.

Probado en Windows 11 (26200) sobre ARM64, con Python 3.13.
