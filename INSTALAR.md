# Instalar Claude Pet

## Qué permisos pide

**Casi ninguno**, y eso es a propósito:

| Permiso | ¿Lo pide? |
|---|---|
| Archivos | **No.** Solo lee `~/.claude.json` y `~/.claude/pet-usage.json`. El home no está protegido por TCC (a diferencia de Escritorio, Documentos y Descargas), así que macOS no pregunta nada. |
| Red | **No.** La app nunca abre una conexión. |
| Automatización / AppleScript | **No.** |
| Accesibilidad | **No.** |
| Grabación de pantalla | **No.** |
| Cámara, micrófono, ubicación, contactos… | **No.** |
| **Notificaciones** | Sí, **una vez** — y solo la primera vez que de verdad haya algo que avisar (al cruzar el 50 %). Si nunca llegas ahí, nunca te pregunta. |
| **Ítems de inicio** | Solo si activas «Abrir al iniciar sesión». Usa `SMAppService`, la API nativa: no muestra ningún diálogo y se quita desde Ajustes → General → Ítems de inicio. |

Para verificarlo en cualquier momento:

```bash
ClaudePet.app/Contents/MacOS/ClaudePet --dump
```

### Diagnóstico en planes Team y Enterprise

Esos planes se miden en dinero y no he podido probarlos con datos reales. Si algo
no cuadra, este comando vuelca el bloque de cuota **quitando todo lo que identifica
a la cuenta** (UUID, correos, tokens, ids), para poder compartirlo sin exponer nada:

```bash
ClaudePet.app/Contents/MacOS/ClaudePet --dump-raw
```

Salen unos 3 KB. Repasa la salida antes de mandarla: lleva tus porcentajes de uso y,
si el plan va por dinero, los importes.

---

## Opción A — compilarla (recomendada)

La más fácil, aunque no lo parezca: al compilarla en tu propia máquina **no hay
cuarentena ni Gatekeeper de por medio**.

```bash
git clone <este-repo> && cd ClaudePet
./build.sh
open ClaudePet.app
```

Requisito único: las Command Line Tools de Apple (gratis, sin Xcode entero).
Si faltan, `build.sh` te lo dice y se instalan con `xcode-select --install`.

---

## Opción B — recibir el `.zip`

`./package.sh` genera un `ClaudePet-1.0.zip` de ~200 KB que lleva dentro la app, este
documento y un **instalador**. Para quien lo recibe es un solo paso:

```bash
bash ~/Downloads/install.sh
```

El instalador copia la app a `/Applications`, le quita la cuarentena, la abre y
pregunta si quiere que arranque al iniciar sesión. (Con `CLAUDEPET_DEST` se puede
instalar en otro sitio, p. ej. `~/Applications`.)

### Por qué hace falta un instalador

Porque **si hace doble clic, macOS no le da salida**. La app va firmada *ad-hoc*, sin
cuenta de desarrollador de Apple. Al descargarla queda con el atributo de cuarentena, y
el diálogo que sale es este:

> **«ClaudePet» no se abrió**
> Apple no pudo verificar que «ClaudePet» esté libre de malware…
> **[Mover a la papelera]** ← el botón azul, el predeterminado
> [Listo]

**No hay botón de «Abrir» ni de «Permitir».** No es un diálogo de permisos que se pueda
aceptar: la única salida que ofrece es borrar la app. Quien no sepa que existe
Ajustes → Privacidad y seguridad → «Abrir igualmente» va a concluir que está rota.

> En macOS 15+ el viejo truco de clic derecho → Abrir tampoco sirve ya.

### El detalle que lo hace funcionar

Lo que dispara el bloqueo es **el atributo de cuarentena**, no el veredicto de
Gatekeeper. Comprobado: tras quitar el atributo, `spctl --assess` sigue diciendo
`rejected` y aun así la app abre sin una sola queja — macOS solo consulta a Gatekeeper
cuando el archivo viene marcado como descargado.

Por eso `xattr -dr com.apple.quarantine` basta, y por eso un script invocado a propósito
desde la Terminal puede hacerlo aunque el doble clic no pueda.

### Para quitar hasta ese paso

Haría falta una cuenta del Apple Developer Program (99 USD/año) para firmar con
Developer ID y notarizar. Para una app que se comparte entre conocidos no compensa: la
Opción A resuelve lo mismo gratis, y la B lo deja en un comando.

## Desinstalar

```bash
./start-at-login.sh --off             # quitar del arranque
rm -rf /Applications/ClaudePet.app    # borrar la app
```

No deja nada más: sus ajustes viven en `~/Library/Preferences/com.mario.claudepet.plist`
y nunca escribe fuera de ahí. Si además instalaste el hook de statusLine,
`./uninstall-statusline.sh` lo revierte.
