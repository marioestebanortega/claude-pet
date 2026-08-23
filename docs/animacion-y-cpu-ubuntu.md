# La animación de la mascota y la CPU — para el agente de Ubuntu

Buenas noticias primero: **la versión de Linux ya lo hace bien.** Este documento no pide
cambiar nada urgente. Existe porque la versión de macOS se comió el 12 % de un núcleo
durante meses por un detalle que parece inofensivo, y quien toque `pet.py` mañana va a
sentir la tentación de cometer exactamente ese error — «suavizar» el movimiento.

## Lo que pasó en macOS

El proceso llevaba **54 minutos de CPU en 7 horas y media** con la mascota quieta en el
escritorio. La causa era esta línea:

```swift
withAnimation(.easeInOut(duration: 1.7).repeatForever(autoreverses: true)) { float = true }
```

Un vaivén de ±1,3 px cada 1,7 s. SwiftUI lo interpola a la cadencia de la pantalla, que
en un Mac con ProMotion son **120 Hz**: 108 fotogramas intermedios que nadie llega a ver,
repintando el sprite entero cada uno.

### La medición

Banco de pruebas que levanta **solo la ventana flotante** (sin barra de menús), apagando
un sospechoso cada vez, 40 s de reloj por medida, dividiendo el incremento de tiempo de
CPU entre el tiempo transcurrido:

| Qué se apagó | CPU |
|---|---|
| nada (como estaba) | 11,2 % |
| el material translúcido del plato | 13,4 % |
| el sprite rasterizado (`drawingGroup()`) | 12,5 % |
| la animación del spinner de «cargando» | 12,7 % |
| **el vaivén** | **0,5 %** |

Lo que hay que llevarse de esa tabla: **ninguno de los sospechosos caros tenía la culpa.**
Ni el desenfoque en vivo, ni las ~180 celdas del lienzo, ni la sombra. Todo eso era ruido
alrededor del 12 % de partida. Era el movimiento, y solo el movimiento.

### Y bajar los fotogramas no arregla nada

Fue lo primero que se probó, y es la parte contraintuitiva:

| Cadencia del vaivén | CPU |
|---|---|
| 120 fps (como estaba) | 11,2 % |
| 30 fps | 3,9 % |
| 15 fps | **3,8 %** |
| dos posiciones, un salto cada 0,9 s | **0,0 %** |

De 30 a 15 fps no bajó nada. **Cualquier movimiento interpolado tiene un suelo de ~4 %**,
por debajo del cual no se llega bajando la frecuencia. Lo que se paga no es dibujar: es
tener un ciclo de animación vivo.

La solución fue quitar la interpolación, no reducirla. La app entera instalada pasó de
~18 % a **1,4 %**.

## Qué hace hoy la versión de Linux (y por qué está a salvo)

Ya funciona a saltos, que es justo lo correcto:

```python
# pet.py:334
GLib.timeout_add(1700, self._breathe)

# pet.py:437
def _breathe(self) -> bool:
    self._bob = BOB if self._bob < 0 else -BOB     # dos posiciones, sin interpolar
    self.queue_draw()
    return True
```

Un redibujado cada 1,7 s. Los demás temporizadores tampoco aprietan: `hub.py` sondea
cada 5 s, y el resto (`400 ms` para guardar la posición al soltar, `2,8 s` para terminar
el saludo) son de un solo disparo.

GTK ayuda aquí sin querer: no tiene animación implícita, así que hay que pedir cada
fotograma a mano. Eso hace difícil caer en el problema por accidente — pero muy fácil
caer en él **a propósito**, buscando que se vea más fino.

## Lo que sí hay que hacer

1. **Medirlo en una Ubuntu de verdad.** En macOS nunca se midió y por eso duró meses.
   Con la mascota en pantalla y sin tocar nada:

   ```bash
   pid=$(pgrep -f "python3 -m claudepet" | head -1)
   leer() { awk '{print $14+$15}' /proc/$pid/stat; }   # utime + stime, en jiffies
   a=$(leer); sleep 60; b=$(leer)
   echo "CPU: $(echo "scale=2; ($b-$a)/$(getconf CLK_TCK)/60*100" | bc) %"
   ```

   Esperado: por debajo del 1 %. Si sale más, el culpable no es el bob — busca otro
   redibujado.

2. **Medir también el compositor.** En Wayland/GNOME una ventana ARGB siempre encima la
   recompone `gnome-shell`, y ese coste no aparece en el proceso propio:

   ```bash
   pidstat -p $(pgrep -x gnome-shell) 5 4        # con la mascota visible y sin ella
   ```

   Si la diferencia es apreciable, dilo en `linux/README.md` con el número: es
   información honesta para quien decida si deja la mascota en el escritorio.

3. **Anotar los números medidos** en `linux/README.md`, como hace el README de macOS.
   Este repo documenta con cifras, no con adjetivos.

4. **Opcional**: la cadencia de macOS quedó en 0,9 s y la de Linux está en 1,7 s. A 0,9 s
   respira más y sigue costando cero. Es cuestión de gusto — si lo cambias, vuelve a
   medir y déjalo escrito.

## Lo que NO hay que hacer

- **No suavizar el vaivén.** Ni con `add_tick_callback()` (el reloj de fotogramas de
  GTK), ni con un `timeout_add(16, ...)`, ni interpolando la posición con una sinusoide.
  Se ve un pelín mejor y cuesta entre 4 % y 12 % de un núcleo, permanentemente, en el
  portátil de alguien. La tabla de arriba es el precio real.
- **No optimizar lo que no es.** Si algún día sube el consumo, no empieces por el
  desenfoque, la sombra ni el número de celdas: en macOS los tres resultaron inocentes.
  Empieza apagando el movimiento, que es la medición que parte el problema en dos.
- **No cachear el sprite en una superficie creyendo que arregla esto.** En macOS
  rasterizarlo (`drawingGroup()`) no cambió nada: 12,5 % contra 12,2 %. El coste no es
  dibujar los píxeles, es despertar.
- **No tocar nada de macOS.** Ese lado ya está arreglado y medido (commit `b3e02db`).

## El encargo, en concreto

No hay que cambiar código. Es solo cerrar la medición que en macOS nunca se hizo:

1. Con la mascota visible en el escritorio y sin tocar nada:
   ```bash
   ./linux/medir-cpu.sh 60
   ```
   Mide el proceso y el compositor a la vez, leyendo `/proc` — no `top`, cuyo `%CPU` es
   una media que arrastra toda la vida del proceso.
2. Repetirlo con la mascota oculta (clic derecho → «Ocultar del escritorio»). La
   diferencia en el compositor es el coste que la mascota provoca **fuera** de su propio
   proceso, y que no aparece en ninguna otra medición.
3. Anotar las dos cifras en `linux/README.md`, en la sección «Por qué la mascota se mueve
   a saltos», con el mismo formato de tabla que usa el README de macOS.

**Criterio**: se espera el proceso por debajo del 1 %. Si sale por encima, el culpable no
es el vaivén — busca otro redibujado antes de tocar la animación, y usa el método de la
tabla de arriba: apagar un sospechoso cada vez y medir, en vez de optimizar a ojo.

Si el compositor sube de forma apreciable con la mascota visible, dilo en el README con
el número. Es información honesta para quien decida si la deja en el escritorio o se
queda solo con el applet de bandeja.

## La regla, en una línea

En una mascota de escritorio, **el movimiento continuo se paga a precio de reloj, no de
píxeles**. Dos posiciones y un temporizador lento cuestan cero y, en pixel-art, además se
ven mejor: los sprites de toda la vida nunca interpolaron entre fotogramas.
