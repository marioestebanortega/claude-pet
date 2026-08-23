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
*file watcher* que reacciona al instante cuando el archivo cambia.

### Frescura del dato

`~/.claude.json` **solo se reescribe cuando Claude Code consulta al servidor**. Entre
consulta y consulta el archivo se queda quieto, así que los números pueden estar viejos
sin que nada haya fallado — es la causa más probable de ver un porcentaje que no coincide
con `/usage`.

Por eso pasados **15 minutos** la app lo dice sin ambigüedad:

- el badge de la mascota se pone gris con un ⏱, en vez del color del humor
- el panel marca la antigüedad en naranja y sugiere instalar el hook

Con el hook de `statusLine` instalado esto deja de pasar: se refresca en cada render de
la barra de estado, o sea constantemente mientras usas Claude Code.

## Uso

```bash
./build.sh          # compila (no necesita Xcode, basta con Command Line Tools)
open ClaudePet.app  # arranca
```

- **Barra de menús** → `😺 25%`. Clic abre el panel con las barras, los reinicios y los ajustes.
- **Mascota de escritorio** → arrástrala donde quieras; clic = releer; pasa el mouse para ver el detalle.
  Si se te pierde en otro monitor, usa **«Traer a Clawd a esta pantalla»** en el panel.
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

## Extras

```bash
./start-at-login.sh        # arranca sola al iniciar sesión
./install-statusline.sh    # datos más frescos vía hook de statusLine (opcional)
./uninstall-statusline.sh  # revertir lo anterior
./ClaudePet.app/Contents/MacOS/ClaudePet --dump   # diagnóstico por consola
```

`install-statusline.sh` hace copia de seguridad de tu `~/.claude/settings.json`
antes de tocarlo y te avisa si ya tenías otro `statusLine`.

## Estructura

```
Sources/main.swift    todo el código (modelo, lectura local, UI, ventana flotante)
build.sh              compila y empaqueta ClaudePet.app
statusline-pet.py     hook opcional de statusLine
```
