# Claude Pet para Linux

Applet de bandeja que vigila tu consumo de Claude Code. Mismo motor que la versión
de macOS, reescrito en Python: **la app de macOS no se puede portar**, sus cinco
frameworks (SwiftUI, AppKit, Combine, UserNotifications, ServiceManagement) son
exclusivos de Darwin.

> **La mascota flotante ya está.** Clawd vive suelto en el escritorio, como en macOS:
> ventana sin marco, siempre encima, arrastrable. El encargo original, con la
> especificación visual y la imagen de referencia, está en
> [`docs/mascota-flotante-ubuntu.md`](../docs/mascota-flotante-ubuntu.md).

## Instalar en Ubuntu

```bash
sudo apt install ./claudepet_1.2_all.deb
claudepet &
```

Se eligió `.deb` y no AppImage a propósito: **`apt` resuelve solo las dependencias**
(`python3-gi`, `python3-gi-cairo` y el indicador de bandeja). Con un AppImage la persona tendría que
instalarlas a mano de todas formas, porque GTK no se puede empaquetar de forma
razonable.

Para que arranque al iniciar sesión:

```bash
claudepet --autostart        # off para quitarlo
```

## El dato fresco: el hook de `statusLine`

Hay dos fuentes y la app las **fusiona**, pero solo una se refresca de verdad:

| Fuente | Cada cuánto | Qué trae |
|---|---|---|
| `~/.claude.json` | muy de tarde en tarde — en la máquina de referencia, **una vez en 22 minutos** | todas las dimensiones, el gasto y los créditos de empresa |
| `~/.claude/pet-usage.json` | cada 10 s, lo escribe el hook | solo sesión y semana, pero al día |

Sin el hook la mascota va con lo que haya en `~/.claude.json`, que puede ser de hace
media hora. Se pone con:

```bash
claudepet --install-statusline        # off para quitarlo
```

Copia el hook a `~/.claude/statusline-pet.py` y añade la entrada a
`~/.claude/settings.json`, con copia de seguridad antes de tocarlo y avisando si ya
tenías otro `statusLine` puesto (en ese caso `off` no te lo borra). Reinicia Claude
Code después.

### Varias sesiones de Claude Code a la vez

**Todas las sesiones abiertas escriben el mismo `pet-usage.json`.** Una que lleve horas
quieta sigue rindiendo su línea de estado cada pocos segundos: reescribe sus cifras de
entonces con marca de tiempo de ahora. Sin más, la mascota rebota entre el dato bueno y
el viejo, y lo que se ve es un número que no coincide con `/usage`.

Se resuelve por los dos lados:

- **Al escribir**, el hook funde en vez de sobrescribir, mirando `resets_at`, que
  identifica la ventana: ventana posterior manda, ventana anterior se ignora, y dentro
  de la misma ventana gana el porcentaje mayor, porque el consumo solo sube. El candado
  es `flock` sobre un archivo aparte, `pet-usage.json.lock`, porque la escritura es
  atómica y cambia de inodo en cada pasada.
- **Al leer**, `usage.py` descarta las ventanas ya vencidas (`_drop_expired`), que es
  justo la forma en que una foto vieja se delata.

Queda un límite que no se puede tapar desde aquí: `written_at_ms` es la hora de
escritura, no la del dato. Si **todas** las sesiones estuvieran quietas el archivo
parecería fresco con cifras viejas, y en el payload no hay ninguna marca de cuándo el
servidor las dio.

## Sin instalar nada

```bash
cd linux && python3 -m claudepet --dump
```

`--dump` **no importa GTK a propósito**, así que funciona aunque falten las
dependencias del escritorio. Es lo primero que hay que probar en una máquina nueva:
si esto muestra tus cifras, el problema es solo de interfaz.

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

Una ventana sin marco y con fondo transparente, siempre por encima del escritorio:
el plato, los dos anillos (el exterior es la semana, el interior la sesión), Clawd
dentro y el badge con `sesión/semana %`.

| Gesto | Qué hace |
|---|---|
| Arrastrar | la mueve |
| Clic izquierdo | saluda, y de paso relee los archivos (gratis) |
| Pasar el ratón | sesión, semana y antigüedad del dato |
| Clic derecho | ocultar, actualizar, traer a esta pantalla, salir |

Se esconde y se saca desde la bandeja, con «Mascota en el escritorio». Lo que esté
visible y dónde estaba se guarda en `~/.config/claudepet/state.json`.

### Wayland: la posición no se puede restaurar

Ubuntu arranca GNOME sobre Wayland, y ahí **una aplicación no puede colocarse sola
en la pantalla**: `Gtk.Window.move()` se ignora sin dar error. Consecuencias:

- La mascota aparece donde la ponga el compositor, no donde la dejaste.
- «Traer a esta pantalla» no hace nada en Wayland; en X11 sí.
- **La posición no se guarda en Wayland.** El cliente tampoco sabe dónde está:
  `configure-event` siempre trae (0, 0). Guardar eso pisaría con un valor falso
  la posición buena de una sesión X11 anterior, así que se deja como estaba.

Lo que sí funciona en Wayland: la transparencia, mantenerse encima y **arrastrarla**,
porque de eso se encarga el compositor (`begin_move_drag`).

No se usa `gtk-layer-shell` a propósito: es una dependencia más y **Mutter no
implementa `wlr-layer-shell`**, así que en GNOME no arreglaría nada.

### Comprobar el dibujo sin escritorio

```bash
python3 -m claudepet --pet-png /tmp/pet.png --night
```

Usa `cairo.ImageSurface`, así que no necesita pantalla, y sale con el mismo encuadre
que `docs/mascota-flotante.png` para poder compararlos píxel a píxel.

## Varias sesiones de Claude Code a la vez

Todas escriben el mismo `~/.claude/pet-usage.json`, y una sesión quieta reescribe sus
cifras viejas con marca de tiempo nueva: la mascota acaba enseñando un número que no
coincide con `/usage`. La mitad del arreglo ya está aquí — `usage.py` descarta ventanas
cuyo `resets_at` quedó atrás. La otra mitad vive en el hook, que **todavía no se
distribuye en el `.deb`**: el encargo completo está en
[`docs/sesiones-simultaneas-ubuntu.md`](../docs/sesiones-simultaneas-ubuntu.md).

## Construir el paquete

```bash
python3 linux/build-deb.py
```

Funciona **desde cualquier sistema, incluido un Mac**: el formato `ar` del `.deb` se
escribe a mano en vez de llamar a `dpkg-deb`.

## Por qué la mascota se mueve a saltos

Porque moverse suave se paga a precio de reloj. En macOS, un vaivén interpolado de
±1,3 px costaba el 12 % de un núcleo todo el rato, y bajarlo a 15 fps no ayudaba: el
suelo de cualquier movimiento continuo era ~4 %. Aquí ya se hace bien — `_breathe()`
alterna dos posiciones cada 1,7 s y no interpola nada.

Medido en Ubuntu 26.04 (GNOME sobre Wayland, arm64), con `./medir-cpu.sh`, leyendo
`utime + stime` de `/proc`. Tres muestras de 30 s por estado, alternando:

| Estado | Proceso | `gnome-shell` |
|---|---|---|
| mascota en el escritorio | **0,07 %** | 0,9 % |
| solo el applet de bandeja (`--no-pet`) | 0,07 % | 0,9 % |

**El proceso cuesta lo mismo con la mascota que sin ella**, muy por debajo del 1 % que
se esperaba. El redibujado cada 1,7 s no se nota.

Del compositor solo se puede decir el límite, no la cifra: `gnome-shell` osciló entre
0,6 % y 3,8 % **en los dos estados**, según lo que estuviera haciendo el resto del
escritorio. Las medianas salen iguales (0,9 % contra 0,9 %), así que el coste que la
mascota provoca fuera de su proceso queda **por debajo del ruido de la medición, unos
±3 puntos**. Con este método no se puede afinar más: hay que medir con el escritorio
quieto, sin una terminal repintándose al lado.

La cadencia se queda en 1,7 s. En macOS quedó en 0,9 s, que respira más y también cuesta
cero; cambiarla aquí obligaría a volver a medir y no hay motivo, porque ya está en el
suelo.

El porqué completo, con la tabla de macOS que descarta a los sospechosos caros:
[`docs/animacion-y-cpu-ubuntu.md`](../docs/animacion-y-cpu-ubuntu.md).

## Qué comparte con la versión de macOS

Todo el criterio, verificado dando las mismas cifras:

- Las dos fuentes locales, **fusionadas** y no elegidas — el hook de `statusLine` es
  más fresco pero solo trae dos ventanas, mientras `~/.claude.json` trae el gasto y
  los créditos de los planes de empresa
- Todas las dimensiones, incluidas las que no conoce (`kind` desconocido → etiqueta
  legible, nunca descartado)
- Planes medidos en dinero: `spend`, `extra_usage` y `used_dollars` / `limit_dollars`
- El humor sale del **peor** límite, no solo de sesión y semana
- Aviso de dato viejo solo si Claude Code está corriendo
- Explicación clara cuando no hay suscripción (API key, Bedrock, Vertex)
- Gorrito de dormir entre las 6 p.m. y las 6 a.m.

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

`draw_pet()` no depende de la ventana a propósito: por eso `--pet-png` puede
comprobar todo el dibujo sin pantalla ninguna.

## Qué está probado y qué no

Probado en Ubuntu 26.04 con GNOME sobre Wayland:

- El motor de datos, contra datos reales y contra un plan de empresa simulado.
- El applet de bandeja: arranca, registra el icono y enseña las cifras.
- El dibujo de la mascota, comparado píxel a píxel con `docs/mascota-flotante.png`:
  plato, anillos y sprite coinciden con la referencia de macOS.
- El `.deb`, instalado con `apt` en la máquina tal cual.

Lo que la referencia **no** puede dar es la tipografía del badge: macOS usa SF Rounded,
que no existe en Linux. Aquí se pide «Ubuntu» y fontconfig sustituye si falta, así que
la cápsula sale de un ancho ligeramente distinto. Es la única diferencia visible.

Si algo falla al arrancar, `--dump` te dirá si el problema son los datos o el
escritorio, y `--pet-png` si es el dibujo o la ventana.
