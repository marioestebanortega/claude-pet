# Claude Pet para Linux

Applet de bandeja que vigila tu consumo de Claude Code. Mismo motor que la versión
de macOS, reescrito en Python: **la app de macOS no se puede portar**, sus cinco
frameworks (SwiftUI, AppKit, Combine, UserNotifications, ServiceManagement) son
exclusivos de Darwin.

> **Pendiente: la mascota flotante.** En macOS Clawd también vive suelto en el
> escritorio; en Linux todavía no. El encargo completo, con la especificación visual y
> la imagen de referencia, está en
> [`docs/mascota-flotante-ubuntu.md`](../docs/mascota-flotante-ubuntu.md).

## Instalar en Ubuntu

```bash
sudo apt install ./claudepet_1.0_all.deb
claudepet &
```

Se eligió `.deb` y no AppImage a propósito: **`apt` resuelve solo las dependencias**
(`python3-gi` y el indicador de bandeja). Con un AppImage la persona tendría que
instalarlas a mano de todas formas, porque GTK no se puede empaquetar de forma
razonable.

Para que arranque al iniciar sesión:

```bash
claudepet --autostart        # off para quitarlo
```

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
  sin argumentos      arranca el applet de bandeja
```

## Construir el paquete

```bash
python3 linux/build-deb.py
```

Funciona **desde cualquier sistema, incluido un Mac**: el formato `ar` del `.deb` se
escribe a mano en vez de llamar a `dpkg-deb`.

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
claudepet/tray.py      la ÚNICA parte que depende de GTK
claudepet/__main__.py  --dump, --icon, --autostart
build-deb.py           empaqueta el .deb
```

## Qué NO está probado

`tray.py` **no se ha ejecutado nunca**: se escribió desde un Mac sin Docker ni
máquina virtual, así que la parte de GTK y AppIndicator solo está comprobada a nivel
de sintaxis. Todo lo demás sí: el motor de datos se probó contra datos reales y
contra un plan de empresa simulado, y el `.deb` se desempaquetó y se ejecutó tal y
como quedaría instalado.

Si el applet falla al arrancar, `--dump` te dirá si el problema son los datos o GTK.
