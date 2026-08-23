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

`./package.sh` genera un `ClaudePet-1.0.zip` de ~200 KB. Funciona, pero hay un
paso extra ineludible.

**Por qué:** la app va firmada *ad-hoc*, sin cuenta de desarrollador de Apple.
La firma es válida (`codesign --verify` pasa), pero Gatekeeper la rechaza igual
porque no tiene Developer ID ni está notarizada. Al descomprimir, macOS le pone
el atributo de cuarentena y se niega a abrirla.

Tras descomprimir, **una** de estas dos:

```bash
xattr -dr com.apple.quarantine /ruta/a/ClaudePet.app
```

O bien: intentar abrirla, dejar que macOS la bloquee, e ir a
**Ajustes → Privacidad y seguridad → «Abrir igualmente»**.

> En macOS 15+ el viejo truco de clic derecho → Abrir ya no sirve.

**Para quitar ese paso** haría falta una cuenta del Apple Developer Program
(99 USD/año) para firmar con Developer ID y notarizar. Para una app que se
comparte entre conocidos no compensa; la Opción A resuelve lo mismo gratis.

---

## Desinstalar

```bash
./start-at-login.sh --off     # quitar del arranque
rm -rf ClaudePet.app          # borrar la app
```

No deja nada más: sus ajustes viven en `~/Library/Preferences/com.mario.claudepet.plist`
y nunca escribe fuera de ahí. Si además instalaste el hook de statusLine,
`./uninstall-statusline.sh` lo revierte.
