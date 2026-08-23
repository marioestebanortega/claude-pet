# 🦞 Claude Pet

**Clawd**, la mascota oficial de Claude Code, vigilando tu consumo desde la barra de
menús y como bicho flotante en el escritorio. Cambia de cara según cuánta cuota llevas.

El sprite no es una imagen: la rejilla de 11 × 8 celdas se extrajo de `clawd.svg`
(la extensión oficial de Claude Code para VS Code) y se redibuja en SwiftUI celda por
celda. Por eso puede parpadear, caminar, mover los bracitos y cambiar de expresión.

## Lo importante: no consume tu cuota

Lee los datos de un **caché local** que Claude Code ya escribe en tu Mac:

| Fuente | Costo | Cuándo se actualiza |
|---|---|---|
| `~/.claude.json` → `cachedUsageUtilization` | **0** | sola, mientras usas Claude Code |
| `~/.claude/pet-usage.json` (hook `statusLine`, opcional) | **0** | en cada render de la barra de estado |
| Botón «Forzar» → `claude -p "/usage"` | **1 request** | solo si tú lo pulsas |

La app usa siempre la fuente **más reciente** de las dos gratuitas, con un
*file watcher* que reacciona en menos de un segundo, más un sondeo cada 10 s como red
de seguridad (leer cuesta ~0 ms, y solo re-parsea si cambió el `mtime`).

> El watcher tiene una trampa que costó un bug: al re-armarse tras una escritura
> atómica, el handler de cancelación de la fuente vieja **no puede leer una propiedad
> `fd`**. Corre en la cola principal, o sea después de que `fd` ya apunta al descriptor
> nuevo, y lo cierra. Hay que capturar el descriptor propio en el closure.

### Frescura del dato — instala el hook

**Medido en esta máquina: `~/.claude.json` se refrescó una sola vez en 22 minutos**, y eso
con Claude Code abierto y en uso. Como fuente única no basta.

La solución es el hook de `statusLine`, y es gratis: Claude Code se lo pasa a un script
local que corre en tu máquina, sin tokens ni red. `./install-statusline.sh` lo deja
configurado así:

```json
{ "type": "command", "command": "python3 ~/.claude/statusline-pet.py",
  "refreshInterval": 10, "padding": 1 }
```

`refreshInterval` es la clave. Sin él, [la línea de estado solo se re-ejecuta tras cada
mensaje del asistente](https://code.claude.com/docs/es/statusline#how-status-lines-work),
así que si dejas Claude Code quieto el dato se congela igual. Con él corre también en
temporizador. Verificado: el archivo se reescribe cada ~10 s y la app lo lee al instante.

### Cuándo avisa de dato viejo

Sin el hook, los números pueden quedarse viejos sin que nada haya fallado — es la causa
más probable de ver un porcentaje que no coincide con `/usage`. Pasados **15 minutos** la
app lo dice sin ambigüedad:

- el badge de la mascota se pone gris con un ⏱, en vez del color del humor
- el panel marca la antigüedad en naranja y sugiere instalar el hook

Pero solo avisa **si Claude Code está corriendo**. Con Claude Code cerrado tu cuota no se
mueve, así que un dato de hace horas sigue siendo correcto y el aviso sería puro ruido.
Se detecta por el `mtime` de los dos archivos, que es un `stat` — sin lanzar procesos ni
pedir permisos.

## Uso

```bash
./build.sh          # compila (no necesita Xcode, basta con Command Line Tools)
open ClaudePet.app  # arranca
```

- **Barra de menús** → `😺 25%`. Clic abre el panel con las barras, los reinicios y los ajustes.
- **Mascota de escritorio** → arrástrala donde quieras; pasa el mouse para ver el detalle.
- **Clic sobre Clawd** → sonríe: entorna los ojos, curva la boca y da un saltito, con un
  saludo en el bocadillo. Dura 2,8 s y vuelve solo. De paso relee el archivo, que es gratis.
- **Clic derecho sobre Clawd** → menú con lo que más se busca:

  | | |
  |---|---|
  | **Ocultar del escritorio** | se queda solo en la barra de menús |
  | Actualizar ahora | vuelve a leer el archivo local |
  | Que haga algo 🎲 | dispara una actividad |
  | Actividades automáticas | apaga o enciende las ocurrencias |
  | Traer a esta pantalla | por si se te pierde en otro monitor |
  | Salir de Claude Pet | |

  Para que vuelva al escritorio: el interruptor **«Mascota en el escritorio»** del panel.
- **Notificaciones** → avisa al cruzar 50 %, 70 % y 90 % (solo al subir de nivel, no en cada lectura).

### Humores

| Consumo | Cara de Clawd | Anillo |
|---|---|---|
| < 40 % | ojos normales, sin boca (Clawd original) | verde |
| 40–70 % | boquita abierta | amarillo |
| 70–90 % | ojos como platos + boca de 3 celdas | naranja |
| ≥ 90 % | ojos como platos + bocaza, y rebota más rápido | rojo |
| sin datos | ojos cerrados, quieto | gris |

Clawd conserva su naranja de marca (`#D97757`) siempre; el color del humor va en el
anillo. Si prefieres que él también cambie de color, actívalo en
**«Clawd cambia de color con el humor»**.

### Planes que no se miden en porcentaje

Pro y Max se miden en ventanas de tiempo (5 h y 7 días). **Team y Enterprise se miden
en dinero**, y esas cifras viven en sitios distintos del mismo archivo:

| Dimensión | Dónde vive | Qué muestra |
|---|---|---|
| Ventanas de tiempo | `limits[]` | sesión, semana, y las que traiga el plan (`monthly`, `daily`…) |
| Dinero por ventana | `five_hour.used_dollars` / `limit_dollars` | «US$ 310 de US$ 500» junto al % |
| Gasto | `utilization.spend` | importe y tope, en la moneda de la cuenta |
| Créditos del mes | `utilization.extra_usage` | tope mensual, con sub-ventanas diaria y semanal |

La app **dibuja todo lo que encuentre**, no una lista fija: si un plan trae un `kind`
que no conoce, lo enseña con la etiqueta legible en vez de descartarlo. Y el humor de
Clawd se calcula sobre **la peor de todas** las dimensiones, no solo sesión y semana.

Ojo con una consecuencia: el hook de `statusLine` solo entrega `five_hour` y
`seven_day`. Por eso las fuentes no se eligen, **se fusionan**: las cifras frescas
salen del hook y las dimensiones ricas de `~/.claude.json`.

Si tu sesión no usa una suscripción de Claude.ai (API key, Bedrock, Vertex), no hay
ventanas de límite que publicar — se factura por uso. La app lo dice en vez de dejarte
esperando datos que no van a llegar.

Para probar con datos de otro plan sin tocar los tuyos:

```bash
CLAUDEPET_JSON=/ruta/a/otro.json CLAUDEPET_STATUSLINE_JSON=/nope   ClaudePet.app/Contents/MacOS/ClaudePet --dump
```

### Doble anillo

La mascota lleva dos anillos concéntricos, no uno:

| Anillo | Qué mide | Grosor |
|---|---|---|
| **Exterior** | semana (7 días) | grueso |
| **Interior** | sesión (5 h) | fino |

Cada uno se colorea con su propio humor, así que puedes tener el anillo de semana en
verde y el de sesión en rojo al mismo tiempo. El badge muestra **`sesión/semana`**
(p. ej. `62/25%`), igual que la barra de menús. El panel lleva una leyenda con los dos
anillitos de color por si se te olvida cuál es cuál.

Nota: **no existe un límite mensual** en los datos de Claude Code — solo estas dos
ventanas. Si alguna vez añaden más (`weekly_scoped` ya viene, para modelos concretos),
aparecen solas como barra extra en el panel.

### Colores

Tres papeles distintos, porque un solo color no sirve para todo:

| Uso | Ejemplo (chill) | Por qué |
|---|---|---|
| Relleno (anillo, barras) | `#34C759` | vivo, se ve sobre cualquier fondo |
| Badge de la mascota | `#1E9455` + texto blanco | el verde claro con texto de color no se leía |
| Porcentaje como texto | `#157F45` claro / `#4ADE80` oscuro | cambia con el tema del sistema |

### Animaciones

**En reposo Clawd está quieto**: solo flota suavemente y parpadea cada ~3 s. Nada más.

Cada 45–150 s (al azar) le da por hacer algo durante unos segundos, y luego vuelve al
reposo:

| Actividad | Qué hace | Dura |
|---|---|---|
| ☕ Café | sostiene una taza humeante y da sorbos, inclinándose | 9 s |
| 🥱 Bostezo | cierra los ojos, abre la bocaza y se estira | 3,5 s |
| 💃 Baile | se balancea de lado a lado moviendo los bracitos | 7 s |
| 🏋️ Ejercicio | hace sentadillas con los brazos arriba | 7 s |
| 😴 Siesta | se hunde, cierra los ojos y le salen «Z» flotando | 13 s |
| 🍎 Manzana | se come una manzana a mordiscos (va desapareciendo) | 8 s |
| 🙂 Sonrisa | **solo al hacerle clic**, no sale sola | 2,8 s |

**Gorrito de dormir** 🌙: entre las 6 p.m. y las 6 a.m. Clawd lo lleva puesto — también
en el ícono de la barra de menús — y le dan más ganas de dormir y bostezar que de bailar.

Se apagan todas con el interruptor **«Actividades»**, o se dispara una a mano con
**«Que haga algo ahora 🎲»**. Para verlas todas sin esperar:

```bash
./ClaudePet.app/Contents/MacOS/ClaudePet --demo        # las recorre en bucle
./ClaudePet.app/Contents/MacOS/ClaudePet --demo=nap    # fija una sola
```

#### Cómo está hecho

El sprite se compone por **capas** (`PixelLayer`): cuerpo, cada bracito por separado,
gorrito, y el accesorio de turno. Se dibujan con `Canvas` en vez de vistas SwiftUI —
son ~180 celdas por fotograma y además el pixel-art **no debe interpolar** entre
fotogramas.

Ese es justo el detalle que hay que tener en cuenta: cambiar *qué celdas se dibujan*
no es un valor animable, así que `withAnimation(.repeatForever)` no lo repite —
se activa una vez y se queda. Los fotogramas discretos van con un `Timer` que
incrementa un contador (`beat`); lo continuo (flotar, inclinarse, estirarse) sí va
con modificadores animables sobre el lienzo entero.

## Permisos

Casi ninguno, y a propósito: **sin red, sin Automatización, sin Accesibilidad, sin
acceso a archivos protegidos**. Solo lee dos archivos del home, que macOS no protege
con TCC. Ver [INSTALAR.md](INSTALAR.md) para el detalle y para compartirla con alguien.

Lo único que puede preguntar:

- **Notificaciones**, una vez, y solo la primera vez que haya algo que avisar (50 %).
- **Ítems de inicio**, si activas «Abrir al iniciar sesión» — vía `SMAppService`, que
  no muestra ningún diálogo.

```bash
ClaudePet.app/Contents/MacOS/ClaudePet --dump   # lista los permisos y su estado
```

## Extras

```bash
./start-at-login.sh        # arranca sola al iniciar sesión (--off para quitarlo)
./package.sh               # .zip de ~200 KB para compartir
./install-statusline.sh    # datos más frescos vía hook de statusLine (opcional)
./uninstall-statusline.sh  # revertir lo anterior
./ClaudePet.app/Contents/MacOS/ClaudePet --dump   # diagnóstico por consola
```

`install-statusline.sh` hace copia de seguridad de tu `~/.claude/settings.json`
antes de tocarlo y te avisa si ya tenías otro `statusLine`.

## Linux

Hay una versión para Ubuntu en [`linux/`](linux/README.md), en Python, con applet de
bandeja y paquete `.deb`. La app de macOS **no se puede portar**: sus cinco frameworks
son exclusivos de Darwin. El motor de datos sí es el mismo criterio, y da las mismas
cifras.

## Estructura

```
Sources/main.swift    todo el código (modelo, lectura local, UI, ventana flotante)
build.sh              compila y empaqueta ClaudePet.app
statusline-pet.py     hook opcional de statusLine
```
