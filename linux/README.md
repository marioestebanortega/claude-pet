# Claude Pet para Linux

Applet de bandeja y mascota flotante que vigilan tu consumo de Claude Code. Mismo motor
que la versión de macOS, reescrito en Python: la app de macOS no se puede portar, sus
frameworks (SwiftUI, AppKit, Combine, UserNotifications, ServiceManagement) son
exclusivos de Darwin.

## Instalar en Ubuntu

```bash
sudo apt install ./claudepet_1.2_all.deb
claudepet &
```

`apt` resuelve las dependencias solo (`python3-gi`, `python3-gi-cairo` y el indicador
de bandeja).

```bash
claudepet --autostart        # arrancar al iniciar sesión (off para quitarlo)
```

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
| Clic derecho | ocultar, actualizar, forzar (`/usage`), traer a esta pantalla, salir |

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
claudepet/sprite.py    Clawd en pixel-art + escritor de PNG con zlib
claudepet/hub.py       un solo temporizador y una sola lectura para todos
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
