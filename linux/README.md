# Claude Pet para Linux

Applet de bandeja y mascota flotante que vigilan tu consumo de Claude Code. Mismo motor
que la versión de macOS, reescrito en Python: la app de macOS no se puede portar, sus
frameworks (SwiftUI, AppKit, Combine, UserNotifications, ServiceManagement) son
exclusivos de Darwin.

## Instalar en Ubuntu

**Sin root**, que es lo normal para una app de bandeja de un solo usuario:

```bash
./install-linux.sh --user        # desde la raíz del repo
./install-linux.sh --user off    # y así se quita
```

La app no necesita permisos de administrador para nada: todo lo que escribe está en tu
HOME (`~/.config/claudepet/state.json` y `~/.config/autostart`), y de `~/.claude.json`
solo lee.

Deja el mismo reparto que el `.deb` pero bajo `~/.local`: el paquete en
`lib/claudepet/claudepet`, el hook a su lado (donde lo busca `--install-statusline`), el
lanzador en `bin/claudepet` y el `.desktop` con su icono en `share/`, así que sale en el
menú de aplicaciones igual.

Lo único que no instala son las dependencias del escritorio, porque esas sí viven en
`/usr`. Suelen venir de serie en Ubuntu; si te faltan, `--dump` sigue funcionando y la
bandeja te dice cuál pedir:

```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 \
                 gir1.2-ayatanaappindicator3-0.1
```

### Con `apt`, para toda la máquina

Solo si quieres el paquete instalado para todos los usuarios, o poder quitarlo y
actualizarlo con `apt`. Aquí sí hay una contraseña, y no es de la app: es `apt`, que
escribe en `/usr` y en la base de datos de dpkg.

```bash
./install-linux.sh                              # genera el .deb y lo instala
sudo apt install ./dist/claudepet_1.3_all.deb   # o a mano, si ya lo generaste
```

`apt` resuelve las dependencias solo (`python3-gi`, `python3-gi-cairo` y el indicador
de bandeja). Se quita con `sudo apt remove claudepet`.

```bash
claudepet --autostart        # arrancar al iniciar sesión (off para quitarlo)
```

Esto último no pide contraseña en ninguno de los dos modos: es una entrada `.desktop` en
`~/.config/autostart`.

## El hook de `statusLine` (recomendado)

Hay dos fuentes locales y la app las fusiona, pero solo una se refresca de verdad:

| Fuente | Cada cuánto | Qué trae |
|---|---|---|
| `~/.claude.json` | muy de tarde en tarde (medido: una vez en 22 min) | todas las dimensiones, gasto y créditos de empresa |
| `~/.claude/pet-usage.json` | cada 10 s, lo escribe el hook | solo sesión y semana, pero al día |

Sin el hook la mascota va con lo que haya en `~/.claude.json`, que puede ser de hace
media hora.

```bash
claudepet --install-statusline        # off para quitarlo
```

Copia el hook a `~/.claude/statusline-pet.py` y añade la entrada a
`~/.claude/settings.json`, con copia de seguridad antes y avisando si ya tenías otro
`statusLine` (en ese caso `off` no te lo borra). **Reinicia Claude Code después.**

Si tienes varias sesiones de Claude Code abiertas, todas escriben el mismo
`pet-usage.json`; el hook funde las cifras en vez de sobrescribirlas y la app descarta
las ventanas ya vencidas, así que se ve un solo número coherente.

## Con Claude Code cerrado

El hook solo corre mientras hay una sesión abierta, así que al cerrar Claude Code la cifra
se congela. No es un fallo —con Claude Code cerrado tu cuota tampoco se mueve—, pero la
ventana de 5 h y la de 7 días siguen avanzando y el dato envejece.

Por eso Clawd pide `/usage` él solo cuando hace falta. El interruptor está en la bandeja
y en el clic derecho de la mascota (que con `--pet` es el único que hay), en «Consultar
/usage sola (no gasta tokens)», y viene encendido:

| Plan | Cuándo dispara |
|---|---|
| Pro/Max | solo si el dato pasa de 15 min, o si las cifras llevan ese rato clavadas aunque el hook siga escribiendo (`changed_at_ms`) |
| Team/Enterprise | cada vez que toca el temporizador: esos planes no publican `rate_limits`, así que no hay ninguna fuente que se refresque sola |
| Sin datos | siempre: preguntar es lo único que puede resolverlo |

Con Claude Code abierto alimentando `pet-usage.json` el temporizador salta sin arrancar
nada. El selector «Cada cuánto» (1 / 2 / 5 min) solo aparece en Team/Enterprise: en
Pro/Max no manda, porque dos consultas no pueden caer más juntas que los 15 minutos de
`STALE_AFTER`.

`/usage` no gasta tokens —el CLI lo resuelve sin un turno del modelo: `num_turns` 0,
`total_cost_usd` 0 con `--output-format json`—; lo que cuesta es arrancar el CLI entero.
Medido aquí con `/usr/bin/time`, tres corridas:

| | real | CPU (user+sys) | pico de RAM |
|---|---|---|---|
| 1 | 2,18 s | 1,29 s | 402 MB |
| 2 | 1,61 s | 0,82 s | 406 MB |
| 3 | 1,66 s | 0,82 s | 368 MB |

Son ~0,98 s de CPU por consulta, o sea ~0,1 % de un núcleo en Pro/Max (una cada 15 min) y
hasta ~1,6 % si en Team/Enterprise se pone el intervalo en un minuto. El menú enseña esa
cifra debajo del interruptor para que la decisión no sea a ciegas. Para comparar: la
mascota flotante animada gasta bastante más, y eso se mide con `./medir-cpu.sh`.

La primera vez que consulta sola avisa con una notificación de escritorio
(`notify-send`; si no está `libnotify-bin`, con un diálogo). Es lo que evita que una
acción automática sorprenda, y por eso el interruptor viene encendido en vez de venir
apagado donde no lo encontraría nadie.

Los tres ajustes viven en `~/.config/claudepet/state.json`: `auto_force_enabled`,
`auto_force_seconds` y `auto_force_notified`.

## Sin instalar nada

```bash
cd linux && python3 -m claudepet --dump
```

`--dump` no importa GTK, así que funciona aunque falten las dependencias del escritorio.
Es lo primero que hay que probar en una máquina nueva: si muestra tus cifras, el
problema es solo de interfaz.

```
  --dump              muestra el consumo y sale (no necesita GTK)
  --icon [ruta]       escribe el PNG de Clawd  [--night] [--tint]
  --autostart [off]   arrancar al iniciar sesión
  --install-statusline [off]  pone el hook que da el dato fresco
  --pet               solo la mascota flotante, sin bandeja
  --no-pet            solo la bandeja, sin mascota
  --pet-png [ruta]    vuelca la mascota a PNG  [--night] [--scale=N]
  sin argumentos      bandeja + mascota, según el estado guardado
```

## La mascota flotante

Ventana sin marco y con fondo transparente, siempre por encima del escritorio: el plato,
los dos anillos (el exterior es la semana, el interior la sesión), Clawd dentro y el
badge con `sesión/semana %`.

| Gesto | Qué hace |
|---|---|
| Arrastrar | la mueve |
| Clic izquierdo | saluda, y de paso relee los archivos |
| Pasar el ratón | sesión, semana y antigüedad del dato |
| Clic derecho | ocultar, actualizar, forzar (`/usage`), consultar `/usage` sola, traer a esta pantalla, salir |

Se esconde y se saca desde la bandeja, con «Mascota en el escritorio». Lo visible y su
posición se guardan en `~/.config/claudepet/state.json`.

### Wayland

Ubuntu arranca GNOME sobre Wayland, y ahí una aplicación no puede colocarse sola en la
pantalla (`Gtk.Window.move()` se ignora sin dar error):

- La mascota aparece donde la ponga el compositor, no donde la dejaste.
- «Traer a esta pantalla» no hace nada; en X11 sí.
- La posición no se guarda.

Sí funcionan la transparencia, mantenerse encima y arrastrarla.

## Construir el paquete

```bash
python3 linux/build-deb.py
```

Funciona desde cualquier sistema, incluido un Mac: el formato `ar` del `.deb` se escribe
a mano en vez de llamar a `dpkg-deb`.

## Estructura

```
claudepet/usage.py     lectura y fusión de fuentes — solo librería estándar
claudepet/state.py     ajustes en ~/.config/claudepet/state.json — sin dependencias
claudepet/runner.py    lanza `claude -p /usage` y las notificaciones — sin GTK
claudepet/sprite.py    Clawd en pixel-art + escritor de PNG con zlib
claudepet/hub.py       temporizadores (releer, y pedir /usage sola) y lectura única
claudepet/tray.py      el applet de bandeja (GTK + AppIndicator)
claudepet/pet.py       la mascota flotante: dibujo con Cairo + ventana
claudepet/app.py       arranque: junta bandeja y mascota en un Gtk.main()
claudepet/__main__.py  --dump, --icon, --autostart, --pet, --pet-png
build-deb.py           empaqueta el .deb
```

## Si algo falla

`--dump` te dice si el problema son los datos o el escritorio, y `--pet-png` (que usa
`cairo.ImageSurface`, sin necesidad de pantalla) si es el dibujo o la ventana.

Probado en Ubuntu 26.04 con GNOME sobre Wayland. Única diferencia visible con macOS: la
tipografía del badge — macOS usa SF Rounded, que no existe en Linux, y aquí se pide
«Ubuntu».
