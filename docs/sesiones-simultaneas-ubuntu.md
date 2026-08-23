# Sesiones simultáneas pisándose las cifras — encargo para el agente de Ubuntu

Lo que sigue se diagnosticó y se arregló en macOS el 23 de agosto de 2026. **El
problema es del archivo compartido, no del sistema operativo: en Ubuntu pasa igual.**
Media solución ya está en el repo y funciona en Linux; la otra media no llega, y eso
es lo que hay que hacer aquí.

## El problema, con lo que se midió

Todas las sesiones de Claude Code abiertas escriben el **mismo**
`~/.claude/pet-usage.json`, cada una en cada render de su línea de estado (unos 10 s).
Una sesión que lleva horas quieta **sigue rindiendo**: reescribe sus cifras de entonces
con marca de tiempo de ahora.

Medido con dos sesiones abiertas, sondeando el store cada 2 s:

```
06:34:23  store=2/27%
06:34:27  store=0/26%     ← la otra sesión escribió su foto vieja
06:34:33  store=2/27%
06:34:37  store=0/26%
```

Las dos variantes del archivo, capturadas:

| | `five_hour` | `resets_at` | Veredicto |
|---|---|---|---|
| variante 1 | 0 % | 23 ago **04:00** | ventana ya vencida → dato de un ciclo anterior |
| variante 2 | 2 % | 23 ago 09:00 | ventana actual → dato bueno |

Para la persona esto no se ve como un rebote: se ve como **una mascota congelada en un
número que no coincide con `/usage`**, porque mira de reojo y le toca la variante mala.

## La regla que lo resuelve

Quedarse con la escritura más reciente **no sirve**: la foto vieja también llega recién
escrita (`written_at_ms` es la hora de escritura, no la del dato). Lo que sí distingue
las dos es `resets_at`, que identifica la ventana:

| Comparación con lo ya guardado | Qué se hace |
|---|---|
| ventana posterior | manda el dato nuevo — la anterior ya se reinició |
| ventana anterior | la foto entrante es vieja, se ignora |
| misma ventana | gana el porcentaje mayor: dentro de una ventana el consumo solo sube |

La fusión la hace **el hook antes de escribir**, no los lectores: así hay una sola
verdad en el archivo y todas las líneas de estado enseñan la misma cifra.

El candado es `flock` sobre `pet-usage.json.lock`, un archivo **aparte**: la escritura es
atómica (`os.replace`) y cambia de inodo en cada pasada, así que un candado sobre el
propio archivo no protegería a la siguiente. Si otra sesión lo tiene cogido, esta pasada
no escribe — la otra está guardando la misma verdad y en diez segundos se vuelve a pasar.

Todo eso ya está escrito en `statusline-pet.py`, en la raíz del repo. Es Python puro y
`fcntl.flock` es POSIX: **funciona en Linux tal cual, no hay que portar nada.**

## Qué funciona ya en Ubuntu y qué no

| Pieza | Dónde | ¿En Ubuntu? |
|---|---|---|
| Descartar ventanas vencidas al leer | `linux/claudepet/usage.py` → `_drop_expired()` | ✅ ya está, aplicado a los dos parsers |
| Fusión por ventana + candado | `statusline-pet.py` | ⚠️ el código sirve, pero **no hay forma de instalarlo** |

Ese es el hueco: **el `.deb` no lleva el hook**. `build-deb.py` empaqueta solo
`claudepet/*.py`, el lanzador, el `.desktop` y los iconos. Y `linux/README.md` nombra el
hook como fuente de datos pero nunca dice cómo ponerlo. Quien instale solo el paquete se
queda con `~/.claude.json` como única fuente, que en la máquina de referencia **se
refrescó una sola vez en 22 minutos**.

En macOS eso lo cubre `install-statusline.sh`. Ese script es bash + Python portable
(`~/.claude/`, `python3`, sin nada de Darwin): sirve de referencia directa, pero pedirle
a alguien que clone el repo para instalar un hook cuando ya tiene el `.deb` es un paso de
más.

## El encargo

1. **Empaquetar el hook.** En `build-deb.py`, copiar `statusline-pet.py` (está en la raíz
   del repo, un nivel por encima de `linux/`) a `usr/lib/claudepet/statusline-pet.py`.
   Los `.py` de `claudepet/` se recogen solos recorriendo el directorio; este va aparte
   porque vive fuera.
2. **Añadir `claudepet --install-statusline [off]`.** Que copie el hook a
   `~/.claude/statusline-pet.py` (modo 0755) y escriba en `~/.claude/settings.json`:
   ```json
   { "type": "command", "command": "python3 ~/.claude/statusline-pet.py",
     "refreshInterval": 10, "padding": 1 }
   ```
   `refreshInterval` no es opcional: sin él la línea de estado solo se re-ejecuta tras
   cada mensaje del asistente, así que con Claude Code quieto el dato se congela igual.
   Copia de seguridad de `settings.json` antes de tocarlo, y avisar si ya había otro
   `statusLine` configurado — todo eso está resuelto en `install-statusline.sh`, cópiale
   el criterio. Con `off`, quitar la entrada y dejar el resto del archivo intacto.
3. **No importar GTK en ese flag.** Sigue el patrón de `--dump` y `--icon`: tienen que
   funcionar en una máquina sin escritorio. El nuevo también.
4. **Documentar en `linux/README.md`**: la sección de frescura debe decir cómo instalar
   el hook, y explicar en dos líneas lo de las sesiones simultáneas (que es lo que la
   gente va a googlear cuando vea un número que no cuadra).
5. **Subir `VERSION` a `1.2`** en `build-deb.py` y regenerar `dist/claudepet_1.2_all.deb`
   con `python3 linux/build-deb.py`.

## Cómo probarlo (estos comandos ya se corrieron en macOS y pasan)

Contra un HOME de mentira, para no tocar los datos reales:

```bash
T=/tmp/fakehome; rm -rf $T; mkdir -p $T/.claude
AHORA=$(date +%s); VIEJA=$((AHORA - 9000)); BUENA=$((AHORA + 9000))

# 1. La sesión buena escribe
echo "{\"rate_limits\":{\"five_hour\":{\"used_percentage\":2,\"resets_at\":$BUENA},\"seven_day\":{\"used_percentage\":27,\"resets_at\":$BUENA}}}" \
  | HOME=$T python3 statusline-pet.py

# 2. La sesión vieja escribe su foto de una ventana vencida → debe quedar 2 y 27
echo "{\"rate_limits\":{\"five_hour\":{\"used_percentage\":0,\"resets_at\":$VIEJA},\"seven_day\":{\"used_percentage\":26,\"resets_at\":$BUENA}}}" \
  | HOME=$T python3 statusline-pet.py

# 3. El consumo sube → debe quedar 5 y 28
# 4. La ventana de 5 h se reinicia (resets_at posterior, 0 %) → debe BAJAR a 0
cat $T/.claude/pet-usage.json
```

El caso 4 es el que puede romperse al implementar mal la regla: si te quedas siempre con
el porcentaje mayor sin mirar la ventana, el número se queda pegado para siempre.

Y en una máquina de verdad, con dos sesiones de Claude Code abiertas y el hook puesto:

```bash
python3 -m claudepet --dump          # debe dar una cifra estable, no alternar
```

## Criterios de aceptación

- [ ] `sudo apt install ./claudepet_1.2_all.deb` deja el hook disponible en el sistema.
- [ ] `claudepet --install-statusline` lo activa; `off` lo revierte sin romper
      `settings.json`.
- [ ] `--dump` y `--install-statusline` funcionan sin GTK instalado.
- [ ] Los cuatro escenarios de arriba dan el resultado esperado, el 4 incluido.
- [ ] Con dos sesiones abiertas, leer el archivo veinte veces seguidas da siempre lo mismo.
- [ ] `linux/README.md` explica el hook y el asunto de las sesiones simultáneas.

## Lo que NO hay que hacer

- **No tocar nada de macOS** (`Sources/`, `build.sh`, `install.sh`, `package.sh`,
  `install-statusline.sh`). Este encargo es `linux/`, `dist/` y `docs/`.
- **No reimplementar la fusión en los lectores de Python.** La verdad se decide una vez,
  al escribir. En los lectores solo va la guarda de ventanas vencidas, que ya está.
- **No cambiar el formato del archivo** (`rate_limits` + `written_at_ms`): lo comparten
  la app de macOS y la de Linux, y una versión vieja de cualquiera de las dos tiene que
  seguir leyéndolo.
- **Cero dependencias de pip.** `fcntl`, `json` y `os` son librería estándar.

## Un límite conocido, para que no se persiga

`written_at_ms` es la hora de **escritura**, no la del dato. Si todas las sesiones
estuvieran quietas, el archivo parecería fresco con cifras viejas. No hay en el payload
ninguna marca de cuándo el servidor dio esas cifras, así que no se puede hacer mejor
desde aquí. Lo tapa la otra mitad: los lectores descartan ventanas ya vencidas, que es
justo la forma en que ese dato viejo se delata.
