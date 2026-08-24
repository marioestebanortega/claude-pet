import SwiftUI
import AppKit
import Combine
import UserNotifications
import ServiceManagement

// ─────────────────────────────────────────────────────────────
// MARK: - Modelo
// ─────────────────────────────────────────────────────────────

struct Limit: Identifiable, Equatable {
    let id: String        // "session", "weekly_all", "weekly_scoped:Fable", "spend"…
    let label: String
    let percent: Int
    let resetsAt: Date?
    let isActive: Bool
    let group: String     // "session" | "weekly" | "monthly" | "spend"
    /// Para planes medidos en dinero (Team/Enterprise) o créditos: "12,40 $ de 50 $".
    var detail: String? = nil
}

struct Usage: Equatable {
    var limits: [Limit] = []
    var fetchedAt: Date = Date()
    var source: String = ""       // de dónde salió el dato

    var session: Limit?  { limits.first { $0.id == "session" } }
    var weekly: Limit?   { limits.first { $0.id == "weekly_all" } }

    /// Todo lo demás que traiga el plan: modelos concretos, gasto en dólares,
    /// créditos mensuales, o dimensiones que aún no existían al escribir esto.
    /// Se ocultan las que están a cero y sin cifra, que solo serían ruido.
    private var extra: [Limit] {
        limits.filter { l in
            l.id != "session" && l.id != "weekly_all"
                && (l.percent > 0 || l.detail != nil || l.isActive)
        }
    }

    /// Team/Enterprise no traen "session"/"weekly_all": ahí se cae a las dos
    /// dimensiones con más porcentaje de lo que sí trajo el plan (gasto, créditos…)
    /// en vez de mostrar 0/0% con la cuota real en 2%.
    private var fallbackTop: [Limit] { extra.sorted { $0.percent > $1.percent } }

    var sessionPct: Int { session?.percent ?? fallbackTop.first?.percent ?? 0 }
    var weekPct: Int { weekly?.percent ?? fallbackTop.dropFirst().first?.percent ?? 0 }

    var sessionLabel: String { session != nil ? "sesión" : (fallbackTop.first?.label ?? "sesión") }
    var weekLabel: String { weekly != nil ? "semana" : (fallbackTop.dropFirst().first?.label ?? "semana") }

    /// "US$ 3,03 de US$ 150": solo lo traen los planes que se miden en dinero.
    var sessionDetail: String? { session?.detail ?? fallbackTop.first?.detail }

    /// true si hay una segunda ventana real que mostrar (semana en Pro/Max, o una
    /// segunda bolsa de crédito distinta en Team/Enterprise). Con una sola
    /// dimensión, la UI compacta muestra un solo número en vez de inventar una
    /// "semana" en 0% que no existe.
    var hasSecondary: Bool { weekly != nil || fallbackTop.dropFirst().first != nil }

    /// Texto del badge/barra de menú: "sesión/semana" cuando hay dos ventanas
    /// reales, un solo número cuando el plan solo separa una (Team/Enterprise).
    var compactText: String { hasSecondary ? "\(sessionPct)/\(weekPct)%" : "\(sessionPct)%" }

    /// Lista larga del panel: todo lo extra, salvo lo que ya se repite arriba
    /// como sesión/semana de repuesto.
    var others: [Limit] {
        guard session == nil, weekly == nil else { return extra }
        let shown = Set(fallbackTop.prefix(2).map(\.id))
        return extra.filter { !shown.contains($0.id) }
    }

    /// El número que define el humor: lo más crítico de todo.
    var worst: Int { limits.map(\.percent).max() ?? 0 }

    /// Qué tan viejo es el dato.
    var age: TimeInterval { Date().timeIntervalSince(fetchedAt) }

    /// El caché solo se reescribe cuando Claude Code consulta al servidor, así que
    /// puede quedarse viejo sin que nada falle. Pasado este punto hay que avisarlo:
    /// los números que se ven ya no son los de verdad.
    static let staleAfter: TimeInterval = 15 * 60
    var isStale: Bool { age > Self.staleAfter }
}

/// Lo que Clawd está haciendo ahora mismo. En reposo solo flota y parpadea.
enum Activity: String {
    case idle, coffee, yawn, dance, workout, nap, apple, smile

    var duration: Double {
        switch self {
        case .idle:    return 0
        case .smile:   return 2.8
        case .yawn:    return 3.5
        case .dance:   return 7
        case .workout: return 7
        case .apple:   return 8
        case .coffee:  return 9
        case .nap:     return 13
        }
    }

    /// De noche le da más por dormir y bostezar; de día, por el café y el baile.
    /// `smile` no entra en el sorteo: es una reacción al clic, no una ocurrencia.
    static func random(night: Bool) -> Activity {
        var pool: [Activity] = [.coffee, .yawn, .dance, .workout, .apple, .nap]
        pool += night ? [.nap, .nap, .yawn] : [.coffee, .dance, .workout]
        return pool.randomElement() ?? .yawn
    }
}

enum Palette {
    static func hex(_ v: Int) -> Color {
        Color(red: Double((v >> 16) & 0xFF) / 255,
              green: Double((v >> 8) & 0xFF) / 255,
              blue: Double(v & 0xFF) / 255)
    }

    /// Color que cambia con el tema del sistema (el panel es claro, el escritorio no).
    static func dyn(light: Int, dark: Int) -> Color {
        func ns(_ v: Int) -> NSColor {
            NSColor(red: CGFloat((v >> 16) & 0xFF) / 255,
                    green: CGFloat((v >> 8) & 0xFF) / 255,
                    blue: CGFloat(v & 0xFF) / 255, alpha: 1)
        }
        return Color(nsColor: NSColor(name: nil) { appearance in
            appearance.bestMatch(from: [.aqua, .darkAqua]) == .darkAqua ? ns(dark) : ns(light)
        })
    }
}

enum Mood: Int {
    case chill, ok, alert, panic, broken

    static func from(_ pct: Int) -> Mood {
        switch pct {
        case ..<40:  return .chill
        case ..<70:  return .ok
        case ..<90:  return .alert
        default:     return .panic
        }
    }

    var face: String {
        switch self {
        case .chill:  return "😺"
        case .ok:     return "😼"
        case .alert:  return "🙀"
        case .panic:  return "😿"
        case .broken: return "🫥"
        }
    }

    /// Color de relleno: anillo y barras de progreso. Vivo, se ve sobre cualquier fondo.
    var color: Color {
        switch self {
        case .chill:  return Palette.hex(0x34C759)
        case .ok:     return Palette.hex(0xFFB020)
        case .alert:  return Palette.hex(0xFF8A2B)
        case .panic:  return Palette.hex(0xFF4D4D)
        case .broken: return Palette.hex(0x98989D)
        }
    }

    /// Versión profunda: fondo sólido del badge, con texto blanco encima.
    var deep: Color {
        switch self {
        case .chill:  return Palette.hex(0x1E9455)
        case .ok:     return Palette.hex(0xB07A06)
        case .alert:  return Palette.hex(0xC4551C)
        case .panic:  return Palette.hex(0xC42B2B)
        case .broken: return Palette.hex(0x6E6E73)
        }
    }

    /// El porcentaje como texto suelto. Se oscurece en tema claro y se aclara en oscuro,
    /// porque el color de relleno es demasiado claro para leerse sobre fondo blanco.
    var textColor: Color {
        switch self {
        case .chill:  return Palette.dyn(light: 0x157F45, dark: 0x4ADE80)
        case .ok:     return Palette.dyn(light: 0x8A5E08, dark: 0xFBBF4B)
        case .alert:  return Palette.dyn(light: 0xB2521B, dark: 0xFDA46A)
        case .panic:  return Palette.dyn(light: 0xB32424, dark: 0xFF7A7A)
        case .broken: return Palette.dyn(light: 0x6E6E73, dark: 0xA8A8AD)
        }
    }

    var phrases: [String] {
        switch self {
        case .chill:
            return ["Vamos suaves, dale con todo 😌", "Cuota fresquita, aprovecha",
                    "Todo en orden por acá", "Ni la he sentido, sigue"]
        case .ok:
            return ["Vamos a mitad de camino", "Ritmo bueno, ojo no más",
                    "Ya calentamos motores 🔥", "Medio tanque, tranquilo"]
        case .alert:
            return ["Uy, cuidado con el gasto 👀", "Bájale un poquito, ¿no?",
                    "Se está poniendo caro esto", "Ya casi tocamos techo"]
        case .panic:
            return ["¡Se nos acaba la cuota! 😱", "MODO AHORRO, YA",
                    "Respira. Guarda algo pa' luego", "Estamos en las últimas 💀"]
        case .broken:
            return ["No encuentro tus datos aún 🫠", "Usa Claude Code un momento y vuelvo"]
        }
    }

    func phrase(seed: Int) -> String { phrases[abs(seed) % phrases.count] }
}

// ─────────────────────────────────────────────────────────────
// MARK: - Lectura local (COSTO CERO — no consume cuota)
// ─────────────────────────────────────────────────────────────

enum LocalUsage {
    /// Se puede redirigir con CLAUDEPET_JSON, para probar con datos de otro
    /// tipo de plan o para instalaciones con el home en otro sitio.
    static var claudeJSON: URL {
        if let p = ProcessInfo.processInfo.environment["CLAUDEPET_JSON"], !p.isEmpty {
            return URL(fileURLWithPath: (p as NSString).expandingTildeInPath)
        }
        return FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".claude.json")
    }
    /// Archivo que escribe el hook opcional de statusLine.
    static var statusLineJSON: URL {
        if let p = ProcessInfo.processInfo.environment["CLAUDEPET_STATUSLINE_JSON"], !p.isEmpty {
            return URL(fileURLWithPath: (p as NSString).expandingTildeInPath)
        }
        return FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".claude/pet-usage.json")
    }

    private static let iso: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()

    private static func date(_ s: Any?) -> Date? {
        guard let s = s as? String else { return nil }
        if let d = iso.date(from: s) { return d }
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        return f.date(from: s)
    }

    /// Formatea un importe. `amount_minor` viene en la unidad menor de la
    /// moneda (céntimos), con su propio exponente: 1250 con exponente 2 = 12,50.
    private static func money(_ value: Double, _ currency: String?) -> String {
        let f = NumberFormatter()
        f.numberStyle = .currency
        f.currencyCode = currency ?? "USD"
        f.maximumFractionDigits = value >= 100 ? 0 : 2
        return f.string(from: NSNumber(value: value)) ?? String(format: "%.2f", value)
    }

    private static func minor(_ d: [String: Any]?) -> Double? {
        guard let d, let amount = d["amount_minor"] as? Double else { return nil }
        let exp = (d["exponent"] as? Double) ?? 2
        return amount / pow(10, exp)
    }

    private static func label(kind: String, scope: [String: Any]?) -> String {
        switch kind {
        case "session":     return "Sesión (5 h)"
        case "weekly_all":  return "Semana (todos los modelos)"
        case "monthly":     return "Mes"
        case "daily":       return "Día"
        case "spend":       return "Gasto"
        case "weekly_scoped":
            let model = (scope?["model"] as? [String: Any])?["display_name"] as? String
            let surface = (scope?["surface"] as? [String: Any])?["display_name"] as? String
            return "Semana (\(model ?? surface ?? "acotado"))"
        default:
            // Un plan puede traer dimensiones que aún no existían: mejor
            // enseñarlas legibles que tirarlas a la basura.
            return kind.replacingOccurrences(of: "_", with: " ").capitalized
        }
    }

    /// Descarta ventanas ya vencidas.
    ///
    /// Si `resets_at` quedó atrás, esa cifra es de un ciclo anterior y ya no
    /// dice nada del actual. Pasa de verdad: todas las sesiones de Claude Code
    /// escriben el mismo `pet-usage.json`, y una que lleva horas quieta reescribe
    /// su foto vieja con marca de tiempo nueva. Un minuto de margen para el
    /// desfase de relojes.
    static func dropExpired(_ limits: [Limit]) -> [Limit] {
        limits.filter { l in
            guard let r = l.resetsAt else { return true }
            return r.timeIntervalSinceNow > -60
        }
    }

    /// Lee `~/.claude.json` → `cachedUsageUtilization`. Gratis e instantáneo.
    static func fromClaudeJSON() -> Usage? {
        guard let data = try? Data(contentsOf: claudeJSON),
              let root = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let cached = root["cachedUsageUtilization"] as? [String: Any],
              let util = cached["utilization"] as? [String: Any]
        else { return nil }

        var u = Usage()
        u.source = "~/.claude.json"
        if let ms = cached["fetchedAtMs"] as? Double {
            u.fetchedAt = Date(timeIntervalSince1970: ms / 1000)
        }

        if let arr = util["limits"] as? [[String: Any]] {
            for l in arr {
                let kind = l["kind"] as? String ?? "?"
                let scope = l["scope"] as? [String: Any]
                var id = kind
                if kind == "weekly_scoped" {
                    let m = (scope?["model"] as? [String: Any])?["display_name"] as? String ?? "?"
                    id = "weekly_scoped:\(m)"
                }
                u.limits.append(Limit(
                    id: id,
                    label: label(kind: kind, scope: scope),
                    // Se redondea (no se trunca) para que coincida con el hook de
                    // statusLine: si no, un 49,8% saldría 49 desde aquí y 50 desde
                    // el hook, saltando de humor/aviso según qué fuente ganó.
                    percent: Int((((l["percent"] as? Double) ?? 0)).rounded()),
                    resetsAt: date(l["resets_at"]),
                    isActive: (l["is_active"] as? Bool) ?? false,
                    group: l["group"] as? String ?? kind,
                    detail: dollarDetail(util[kindKey(kind)] as? [String: Any])
                ))
            }
        } else {
            // Respaldo por si algún día desaparece `limits`.
            for (key, lbl) in [("five_hour", "Sesión (5 h)"), ("seven_day", "Semana (todos los modelos)")] {
                guard let d = util[key] as? [String: Any],
                      let pct = d["utilization"] as? Double else { continue }
                u.limits.append(Limit(id: key == "five_hour" ? "session" : "weekly_all",
                                      label: lbl, percent: Int(pct.rounded()),
                                      resetsAt: date(d["resets_at"]),
                                      isActive: true,
                                      group: key == "five_hour" ? "session" : "weekly"))
            }
        }
        // Dimensiones que no viven en `limits[]` y que son justo las que
        // usan los planes de empresa: gasto en dinero y créditos mensuales.
        u.limits.append(contentsOf: spendLimits(util))

        u.limits = dropExpired(u.limits)
        return u.limits.isEmpty ? nil : u
    }

    /// El objeto `utilization` guarda las cifras en dólares aparte de `limits[]`.
    private static func kindKey(_ kind: String) -> String {
        switch kind {
        case "session":    return "five_hour"
        case "weekly_all": return "seven_day"
        default:           return kind
        }
    }

    /// "12,40 $ de 50 $" cuando el plan se mide en dinero en vez de en porcentaje.
    private static func dollarDetail(_ d: [String: Any]?) -> String? {
        guard let d,
              let used = d["used_dollars"] as? Double,
              let limit = d["limit_dollars"] as? Double, limit > 0
        else { return nil }
        return "\(money(used, "USD")) de \(money(limit, "USD"))"
    }

    /// Una ventana de créditos (`extra_usage` y sus sub-ventanas diaria/semanal).
    /// Escala `used_credits`/`monthly_limit` (o `limit`) por `decimal_places`.
    private static func creditLimit(_ d: [String: Any], id: String, label: String,
                                    group: String, scale: Double, currency: String?,
                                    isActive: Bool, resetsAt: Date?) -> Limit {
        let used = (d["used_credits"] as? Double).map { $0 / scale }
        let cap = ((d["limit"] as? Double) ?? (d["monthly_limit"] as? Double)).map { $0 / scale }
        var text: String? = nil
        if let used, let cap { text = "\(money(used, currency)) de \(money(cap, currency))" }
        return Limit(id: id, label: label,
                     percent: Int((((d["utilization"] as? Double) ?? 0)).rounded()),
                     resetsAt: resetsAt, isActive: isActive, group: group, detail: text)
    }

    /// Gasto en dinero (`spend`) y créditos mensuales (`extra_usage`).
    /// En una suscripción Pro/Max vienen vacíos y no se dibuja nada; en Team y
    /// Enterprise son la métrica que de verdad importa.
    private static func spendLimits(_ util: [String: Any]) -> [Limit] {
        let sp = util["spend"] as? [String: Any]
        let spUsed = minor(sp?["used"] as? [String: Any])
        let spCap = minor(sp?["limit"] as? [String: Any]) ?? minor(sp?["cap"] as? [String: Any])
        let spPct = Int((((sp?["percent"] as? Double) ?? 0)).rounded())
        let spCurrency = (sp?["used"] as? [String: Any])?["currency"] as? String
        var spendEntry: Limit? = nil
        if sp != nil, (spCap != nil || spPct > 0 || (spUsed ?? 0) > 0) {
            var text: String? = nil
            if let spUsed, let spCap { text = "\(money(spUsed, spCurrency)) de \(money(spCap, spCurrency))" }
            else if let spUsed, spUsed > 0 { text = money(spUsed, spCurrency) }
            spendEntry = Limit(id: "spend", label: "Gasto", percent: spPct,
                               resetsAt: nil, isActive: (sp?["enabled"] as? Bool) ?? false,
                               group: "spend", detail: text)
        }

        guard let ex = util["extra_usage"] as? [String: Any], (ex["is_enabled"] as? Bool) == true
        else { return spendEntry.map { [$0] } ?? [] }

        // "decimal_places", no "exponent": mismos centavos que `spend`, otra clave.
        let scale = pow(10, (ex["decimal_places"] as? Double) ?? 2)
        let cur = ex["currency"] as? String
        let credits = creditLimit(ex, id: "extra_usage", label: "Créditos del mes",
                                  group: "monthly", scale: scale, currency: cur,
                                  isActive: (ex["spend_limit_reached"] as? Bool) != true,
                                  resetsAt: nil)

        // `spend` y los créditos suelen ser la misma bolsa vista dos veces (mismo
        // usado, mismo tope). Mostrar las dos por separado es el "2/2%" confuso,
        // como si fueran dos ventanas distintas — así que si coinciden, una basta.
        let exUsed = (ex["used_credits"] as? Double).map { $0 / scale }
        let exCap = (ex["monthly_limit"] as? Double).map { $0 / scale }
        let sameBolsa = spUsed != nil && exUsed != nil
            && abs(spUsed! - exUsed!) < 0.01 && abs((spCap ?? -1) - (exCap ?? -2)) < 0.01

        var out: [Limit] = [credits]
        if let spendEntry, !sameBolsa { out.append(spendEntry) }
        // El límite mensual puede llevar sub-ventanas diaria y semanal.
        for (key, name) in [("daily", "Créditos del día"), ("weekly", "Créditos de la semana")] {
            guard let sub = ex[key] as? [String: Any] else { continue }
            out.append(creditLimit(sub, id: "extra_\(key)", label: name,
                                   group: key == "daily" ? "daily" : "weekly",
                                   scale: scale, currency: cur, isActive: false,
                                   resetsAt: date(sub["resets_at"])))
        }
        return out
    }

    /// Lee el archivo del hook de statusLine (formato `rate_limits`).
    static func fromStatusLine() -> Usage? {
        guard let data = try? Data(contentsOf: statusLineJSON),
              let root = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let rl = root["rate_limits"] as? [String: Any]
        else { return nil }

        var u = Usage()
        u.source = "statusLine"
        if let ms = root["written_at_ms"] as? Double {
            u.fetchedAt = Date(timeIntervalSince1970: ms / 1000)
        } else if let attrs = try? FileManager.default.attributesOfItem(atPath: statusLineJSON.path),
                  let m = attrs[.modificationDate] as? Date {
            u.fetchedAt = m
        }

        for (key, lbl, id, grp) in [("five_hour", "Sesión (5 h)", "session", "session"),
                                    ("seven_day", "Semana (todos los modelos)", "weekly_all", "weekly")] {
            guard let d = rl[key] as? [String: Any],
                  let pct = d["used_percentage"] as? Double else { continue }
            var reset: Date? = nil
            if let ts = d["resets_at"] as? Double { reset = Date(timeIntervalSince1970: ts) }
            else { reset = date(d["resets_at"]) }
            u.limits.append(Limit(id: id, label: lbl, percent: Int(pct.rounded()),
                                  resetsAt: reset, isActive: true, group: grp))
        }
        u.limits = dropExpired(u.limits)
        return u.limits.isEmpty ? nil : u
    }

    /// Fecha de modificación de cada fuente. Sirve para no re-parsear en balde:
    /// un `stat` cuesta nada, y así el sondeo puede ser frecuente sin pesar.
    static func stamps() -> [Date?] {
        [claudeJSON, statusLineJSON].map { url in
            (try? FileManager.default.attributesOfItem(atPath: url.path))?[.modificationDate] as? Date
        }
    }

    /// Cuándo se movieron por última vez los porcentajes del hook.
    ///
    /// No es lo mismo que `written_at_ms`: el hook reescribe el archivo cada
    /// ~10 s con marca nueva aunque las cifras no hayan cambiado, porque Claude
    /// Code las refresca a saltos. Por eso `fetchedAt` nunca envejece mientras
    /// haya una sesión viva, y sin esta segunda señal la app no puede distinguir
    /// "recién escrito" de "recién actualizado".
    ///
    /// Devuelve nil si el hook es de una versión anterior a `changed_at_ms`: ahí
    /// no se sabe, y no saber no debe disparar nada.
    static func statusLineChangedAt() -> Date? {
        guard let data = try? Data(contentsOf: statusLineJSON),
              let root = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let ms = root["changed_at_ms"] as? Double
        else { return nil }
        return Date(timeIntervalSince1970: ms / 1000)
    }

    /// ¿Claude Code está corriendo ahora?
    ///
    /// Se deduce del mtime de los dos archivos: Claude Code reescribe
    /// `~/.claude.json` continuamente mientras corre, y con el hook instalado
    /// `pet-usage.json` se refresca cada pocos segundos. Es un `stat`, sin
    /// lanzar procesos ni pedir permisos.
    ///
    /// Importa porque si Claude Code está cerrado, tu consumo no está
    /// cambiando: un dato de hace horas sigue siendo correcto y avisar de
    /// que está "viejo" sería ruido.
    static func claudeCodeActive(within: TimeInterval = 3 * 60) -> Bool {
        let fm = FileManager.default
        for url in [statusLineJSON, claudeJSON] {
            if let attrs = try? fm.attributesOfItem(atPath: url.path),
               let m = attrs[.modificationDate] as? Date,
               Date().timeIntervalSince(m) < within {
                return true
            }
        }
        return false
    }

    /// Por qué no hay datos. Importa distinguir "aún no" de "nunca": a quien use
    /// API key, Bedrock o Vertex no le van a aparecer jamás, y dejarlo esperando
    /// sería mentirle.
    static func emptyReason() -> String {
        guard let data = try? Data(contentsOf: claudeJSON),
              let root = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else {
            return "No encuentro ~/.claude.json. ¿Has usado Claude Code en este Mac?"
        }
        if root["oauthAccount"] == nil {
            return "Tu sesión no usa una suscripción de Claude.ai — parece API key, "
                 + "Bedrock o Vertex. Esos planes se facturan por uso y no publican "
                 + "ventanas de límite, así que no hay nada que vigilar."
        }
        if root["cachedUsageUtilization"] == nil {
            return "Aún no hay cifras de cuota. Usa Claude Code un momento y aparecen."
        }
        return "Tu plan no expone ninguna ventana de límite."
    }

    /// Combina las dos fuentes.
    ///
    /// No basta con quedarse con la más reciente: `statusLine` es más fresco pero
    /// solo trae sesión y semana, mientras que `~/.claude.json` trae además el
    /// gasto en dinero y los créditos, que es lo que miden los planes de empresa.
    /// Así que se toman las cifras frescas y se conservan las dimensiones ricas.
    static func best() -> Usage? {
        let rich = fromClaudeJSON()
        let fresh = fromStatusLine()

        guard let rich else { return fresh }
        guard let fresh, fresh.fetchedAt > rich.fetchedAt else { return rich }

        var out = rich
        for f in fresh.limits {
            if let i = out.limits.firstIndex(where: { $0.id == f.id }) {
                let old = out.limits[i]
                out.limits[i] = Limit(id: old.id, label: old.label,
                                      percent: f.percent,
                                      resetsAt: f.resetsAt ?? old.resetsAt,
                                      isActive: old.isActive, group: old.group,
                                      detail: old.detail)
            } else {
                out.limits.append(f)
            }
        }
        out.fetchedAt = fresh.fetchedAt
        out.source = "statusLine + ~/.claude.json"
        return out
    }
}

// ─────────────────────────────────────────────────────────────
// MARK: - Refresco manual vía CLI (`/usage`, 0 tokens)
// ─────────────────────────────────────────────────────────────

enum ClaudeRunner {
    /// Fuerza a Claude Code a consultar el servidor, lo que reescribe el caché local.
    static func forceRefresh() -> String? {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/bin/zsh")
        p.arguments = ["-c", #"export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"; claude -p "/usage" 2>&1"#]
        p.currentDirectoryURL = FileManager.default.homeDirectoryForCurrentUser
        let pipe = Pipe()
        p.standardOutput = pipe; p.standardError = pipe
        do { try p.run() } catch { return "No pude lanzar el CLI: \(error.localizedDescription)" }

        let watchdog = DispatchWorkItem { if p.isRunning { p.terminate() } }
        DispatchQueue.global().asyncAfter(deadline: .now() + 120, execute: watchdog)
        let out = String(data: pipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
        p.waitUntilExit()
        watchdog.cancel()

        if p.terminationStatus != 0 {
            let s = out.trimmingCharacters(in: .whitespacesAndNewlines)
            return s.isEmpty ? "El CLI salió con código \(p.terminationStatus)" : String(s.prefix(200))
        }
        return nil
    }
}

// ─────────────────────────────────────────────────────────────
// MARK: - Vigilante de archivos (actualización instantánea, gratis)
// ─────────────────────────────────────────────────────────────

/// Observa un archivo y re-arma el watcher cuando lo reemplazan (escritura atómica).
final class FileWatcher {
    private var source: DispatchSourceFileSystemObject?
    private var dirSource: DispatchSourceFileSystemObject?
    private let url: URL
    private let onChange: () -> Void
    private var rearmScheduled = false

    init(url: URL, onChange: @escaping () -> Void) {
        self.url = url
        self.onChange = onChange
        arm()
    }

    /// Se engancha al archivo si existe. Si no existe —el hook de statusLine es
    /// opt-in y su `pet-usage.json` puede no llegar nunca— vigila el directorio
    /// padre a la espera de que aparezca, en vez de reintentar en bucle. Así el
    /// caso "sin hook" (la mayoría) no gasta CPU en reposo.
    private func arm() {
        // ¿Estábamos ya enganchados al archivo? Se lee ANTES de cancelar, para
        // avisar una sola vez cuando el archivo aparece de cero (no en cada
        // re-enganche tras una escritura atómica, que ya avisó en su handler).
        let wasAttached = source != nil

        // Cancelar la fuente anterior ANTES de abrir el descriptor nuevo. Su
        // handler de cancelación cierra el fd que capturó, no uno leído después:
        // como el handler corre en la cola principal, si leyera una propiedad
        // `self.fd` la encontraría ya apuntando al descriptor nuevo y lo cerraría,
        // matando el vigilante en el primer reemplazo del archivo.
        source?.cancel()
        source = nil

        let newFD = open(url.path, O_EVTONLY)
        guard newFD >= 0 else { watchParent(); return }

        // El archivo existe: soltar el vigilante del directorio si lo había.
        dirSource?.cancel()
        dirSource = nil

        let s = DispatchSource.makeFileSystemObjectSource(
            fileDescriptor: newFD,
            eventMask: [.write, .rename, .delete, .extend],
            queue: .main)
        s.setEventHandler { [weak self, weak s] in
            guard let self, let s else { return }
            let ev = s.data
            self.onChange()
            // Escritura atómica (`os.replace`): el inodo vigilado desaparece y
            // hay que volver a engancharse al archivo nuevo.
            if ev.contains(.rename) || ev.contains(.delete) { self.scheduleRearm() }
        }
        s.setCancelHandler { close(newFD) }
        s.resume()
        source = s

        // El archivo acaba de aparecer (veníamos del vigilante de directorio o
        // del arranque sin archivo): leerlo una vez.
        if !wasAttached { onChange() }
    }

    /// Mientras el archivo no exista, vigilar su directorio: cuando algo cambie
    /// ahí (p. ej. lo crea el hook) se reintenta `arm()`. Coste en reposo cero —
    /// solo dispara con cambios reales del directorio, no en un temporizador.
    private func watchParent() {
        guard dirSource == nil else { return }
        let dir = url.deletingLastPathComponent()
        let dfd = open(dir.path, O_EVTONLY)
        guard dfd >= 0 else { return }   // ni el directorio existe: queda el poll
        let ds = DispatchSource.makeFileSystemObjectSource(
            fileDescriptor: dfd,
            eventMask: [.write],
            queue: .main)
        ds.setEventHandler { [weak self] in self?.arm() }
        ds.setCancelHandler { close(dfd) }
        ds.resume()
        dirSource = ds
    }

    private func scheduleRearm() {
        guard !rearmScheduled else { return }
        rearmScheduled = true
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) { [weak self] in
            guard let self else { return }
            self.rearmScheduled = false
            self.arm()
        }
    }

    deinit { source?.cancel(); dirSource?.cancel() }
}

// ─────────────────────────────────────────────────────────────
// MARK: - Estado global
// ─────────────────────────────────────────────────────────────

/// Notificaciones nativas.
///
/// Antes esto era `osascript -e 'display notification'`, que pedía permiso de
/// Automatización y las mostraba a nombre de "Script Editor". Con UserNotifications
/// salen como Claude Pet, el usuario las controla desde Ajustes → Notificaciones,
/// y el permiso se pide UNA vez: la primera que de verdad haya algo que avisar.
@MainActor
final class Notifier: NSObject, ObservableObject, UNUserNotificationCenterDelegate {
    static let shared = Notifier()

    /// Si el usuario las bloqueó, el interruptor del panel no serviría de nada
    /// y hay que decírselo en vez de fallar en silencio.
    @Published private(set) var denied = false

    private var authorized = false
    private var asked = false
    private var pending: (String, String)?

    /// Lee el estado real del sistema; el usuario pudo cambiarlo en Ajustes.
    func refreshStatus() {
        guard available else { return }
        UNUserNotificationCenter.current().getNotificationSettings { st in
            Task { @MainActor in
                self.denied = st.authorizationStatus == .denied
                self.authorized = st.authorizationStatus == .authorized
                                || st.authorizationStatus == .provisional
                self.asked = st.authorizationStatus != .notDetermined
            }
        }
    }

    func openSettings() {
        let url = URL(string: "x-apple.systempreferences:com.apple.Notifications-Settings.extension")!
        NSWorkspace.shared.open(url)
    }

    /// UNUserNotificationCenter necesita un bundle de verdad; suelto no arranca.
    private var available: Bool { Bundle.main.bundleIdentifier != nil }

    func send(title: String, body: String) {
        guard available else { return }
        guard asked else {
            pending = (title, body)
            requestOnce()
            return
        }
        guard authorized else { return }
        deliver(title: title, body: body)
    }

    /// Se pide de forma perezosa: quien nunca llegue al 50 % nunca ve el diálogo.
    private func requestOnce() {
        guard !asked else { return }
        asked = true
        let center = UNUserNotificationCenter.current()
        center.delegate = self
        center.requestAuthorization(options: [.alert, .sound]) { granted, _ in
            Task { @MainActor in
                self.authorized = granted
                self.denied = !granted
                if granted, let (t, b) = self.pending { self.deliver(title: t, body: b) }
                self.pending = nil
            }
        }
    }

    private func deliver(title: String, body: String) {
        let c = UNMutableNotificationContent()
        c.title = title
        c.body = body
        c.sound = .default
        UNUserNotificationCenter.current().add(
            UNNotificationRequest(identifier: UUID().uuidString, content: c, trigger: nil))
    }

    /// Que se vean aunque Clawd tenga el foco.
    nonisolated func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        completionHandler([.banner, .sound])
    }
}

@MainActor
final class PetStore: ObservableObject {
    static let shared = PetStore()

    @Published private(set) var usage: Usage?
    @Published private(set) var forcing = false
    @Published private(set) var errorMsg: String?
    @Published private(set) var noAccess = false
    @Published var demoOld = false
    private var autoForceFailures = 0
    private var lastAutoForce: Date?
    @Published private(set) var bubble: String?
    @Published private(set) var tick = Date()   // para refrescar los "hace X min"
    @Published private(set) var activity: Activity = .idle
    @Published private(set) var claudeActive = false

    /// Solo hay motivo para desconfiar del dato si Claude Code está corriendo:
    /// con Claude Code cerrado la cuota no se mueve.
    var dataLooksStale: Bool { (usage?.isStale ?? false) && claudeActive }

    /// Si el plan publica `rate_limits` (Pro/Max) hay una fuente que se refresca
    /// sola y gratis... mientras Claude Code esté abierto. Team/Enterprise no la
    /// tiene nunca.
    var hasFreeSource: Bool { usage?.session != nil || usage?.weekly != nil }

    /// Cuándo vale la pena gastar un arranque del CLI. En Team/Enterprise, cada
    /// vez que toque el timer: no hay otra fuente. En Pro/Max solo si el dato
    /// local ya está viejo — con Claude Code abierto el hook lo mantiene fresco
    /// y pedir `/usage` sería tirar 1,3 s de CPU para nada. Sin dato ninguno,
    /// preguntar siempre vale la pena.
    /// Las cifras llevan clavadas más de lo que dura una ventana de frescura,
    /// aunque el archivo se siga reescribiendo. Puede ser que Claude Code no las
    /// haya refrescado... o que simplemente no estés consumiendo nada. Desde el
    /// archivo no se distingue, y por eso esto solo sirve para ir a preguntar con
    /// `/usage` —que es barato y resuelve la duda— y nunca para pintar el dato
    /// como viejo, que daría un falso positivo cada vez que te levantas a comer.
    var figuresLookFrozen: Bool {
        guard let changed = LocalUsage.statusLineChangedAt() else { return false }
        return Date().timeIntervalSince(changed) > Usage.staleAfter
    }

    var autoForceIsDue: Bool {
        // Team/Enterprise: no hay ninguna otra fuente, dispara cuando toque.
        if !hasFreeSource { return true }
        // En Pro/Max, como mucho una consulta por ventana. Sin este tope,
        // `figuresLookFrozen` se realimentaría: `/usage` reescribe
        // `~/.claude.json`, no `pet-usage.json`, así que `changed_at_ms` no se
        // mueve y la condición seguiría siendo cierta en el siguiente tic.
        if let last = lastAutoForce, Date().timeIntervalSince(last) < Usage.staleAfter {
            return false
        }
        return (usage?.isStale ?? true) || figuresLookFrozen
    }

    @Published var petVisible: Bool {
        didSet {
            UserDefaults.standard.set(petVisible, forKey: "petVisible")
            onPetVisibilityChange?(petVisible)
        }
    }
    @Published var notifyEnabled: Bool {
        didSet { UserDefaults.standard.set(notifyEnabled, forKey: "notifyEnabled") }
    }
    /// Si está activo, Clawd se pinta del color del humor en vez de su naranja de marca.
    @Published var tintClawd: Bool {
        didSet { UserDefaults.standard.set(tintClawd, forKey: "tintClawd") }
    }
    /// Arranque al iniciar sesión, vía SMAppService.
    ///
    /// Antes esto era un script con AppleScript + System Events, que pedía permiso de
    /// Automatización. SMAppService no pide nada y aparece en Ajustes → General →
    /// Ítems de inicio con el nombre de la app, donde se puede quitar a mano.
    @Published var launchAtLogin: Bool {
        didSet {
            guard !syncingLogin else { return }
            applyLaunchAtLogin(launchAtLogin)
        }
    }
    @Published private(set) var loginError: String?

    /// Ningún plan se refresca solo con Claude Code cerrado: Team/Enterprise no
    /// publica `rate_limits`, y el `rate_limits` de Pro/Max lo escribe el hook de
    /// `statusLine`, que solo corre mientras haya una sesión abierta. Cerrado
    /// Claude Code la cifra se congela y `/usage` es la única forma de traer una
    /// fresca. Es una consulta de estado que no gasta tokens, pero aun así solo
    /// dispara cuando de verdad hace falta (`autoForceIsDue`), y avisa la
    /// primera vez.
    @Published var autoForceEnabled: Bool {
        didSet {
            UserDefaults.standard.set(autoForceEnabled, forKey: "autoForceEnabled")
            scheduleAutoForce()
        }
    }

    /// Cada cuántos segundos se pide `/usage` sola. `/usage` no gasta tokens
    /// (medido: `num_turns` 0, `total_cost_usd` 0), pero cada consulta arranca
    /// el CLI entero: ~1,3 s de CPU y un pico de 580 MB. Por eso es un ajuste y
    /// no una constante, y por eso el mínimo es un minuto y no treinta segundos.
    @Published var autoForceSeconds: Int {
        didSet {
            UserDefaults.standard.set(autoForceSeconds, forKey: "autoForceSeconds")
            scheduleAutoForce()
        }
    }

    /// Si está activo, cada tanto a Clawd le da por hacer algo.
    @Published var activitiesEnabled: Bool {
        didSet {
            UserDefaults.standard.set(activitiesEnabled, forKey: "activitiesEnabled")
            if activitiesEnabled { scheduleActivity() }
            else { activityTimer?.invalidate(); activity = .idle }
        }
    }

    /// Después de las 6 p.m. (y hasta las 6 a.m.) Clawd se pone el gorrito de dormir.
    /// Cuelga de `tick` para que se refresque solo con el temporizador de lectura.
    var isNight: Bool {
        let h = Calendar.current.component(.hour, from: tick)
        return h >= 18 || h < 6
    }
    /// Cada cuánto re-lee el archivo local. Es gratis, así que puede ser seguido.
    @Published var pollSeconds: Int {
        didSet {
            UserDefaults.standard.set(pollSeconds, forKey: "pollSeconds")
            scheduleTimer()
        }
    }

    var onPetVisibilityChange: ((Bool) -> Void)?
    var onRecenterPet: (() -> Void)?

    private var timer: Timer?
    private var activityTimer: Timer?
    private var autoForceTimer: Timer?
    private var syncingLogin = false
    private var lastStamps: [Date?] = []
    private var watchers: [FileWatcher] = []
    private var bubbleTask: DispatchWorkItem?
    private var lastNotifiedStep = -1
    private var lastWorst = -1

    var mood: Mood { noAccess || usage == nil ? .broken : Mood.from(usage!.worst) }

    private init() {
        let d = UserDefaults.standard
        petVisible    = d.object(forKey: "petVisible") as? Bool ?? true
        notifyEnabled = d.object(forKey: "notifyEnabled") as? Bool ?? true
        tintClawd     = d.object(forKey: "tintClawd") as? Bool ?? false
        activitiesEnabled = d.object(forKey: "activitiesEnabled") as? Bool ?? true
        // Encendido por defecto en todos los planes: sin esto, quien cierre
        // Claude Code se queda mirando una cifra congelada y el interruptor no
        // lo encuentra nadie. Lo que evita la sorpresa es el aviso de la primera
        // vez, no venir apagado. Cuánto cuesta de verdad: `autoForceIsDue` no
        // deja que dispare mientras el hook mantenga el dato fresco.
        autoForceEnabled  = d.object(forKey: "autoForceEnabled") as? Bool ?? true
        autoForceSeconds  = d.object(forKey: "autoForceSeconds") as? Int ?? 300
        // La verdad la tiene el sistema, no UserDefaults: el usuario pudo quitarlo
        // a mano desde Ajustes y hay que reflejarlo.
        launchAtLogin = SMAppService.mainApp.status == .enabled
        // El vigilante de archivos ya avisa al instante; esto es la red de
        // seguridad. Como leer cuesta ~0 ms, no hay motivo para espaciarlo.
        pollSeconds   = d.object(forKey: "pollSeconds") as? Int ?? 10
    }

    func start() {
        watchers = [
            FileWatcher(url: LocalUsage.claudeJSON) { [weak self] in
                Task { @MainActor in self?.reload() }
            },
            FileWatcher(url: LocalUsage.statusLineJSON) { [weak self] in
                Task { @MainActor in self?.reload() }
            },
        ]
        scheduleTimer()
        scheduleAutoForce()
        if CommandLine.arguments.contains("--demo=sick") { noAccess = true; scheduleActivity() }
        else if CommandLine.arguments.contains("--demo=old") { demoOld = true; scheduleActivity() }
        else if CommandLine.arguments.contains(where: { $0.hasPrefix("--demo") }) { startDemo() }
        else { scheduleActivity() }
        reload(announce: true)
    }

    /// Pide `/usage` sola cada `autoForceSeconds` si el usuario lo activó, y solo
    /// cuando hace falta (`autoForceIsDue`): en Pro/Max, mientras Claude Code esté
    /// abierto alimentando `pet-usage.json`, el timer salta sin arrancar nada.
    /// `/usage` no gasta tokens en ningún plan.
    private func scheduleAutoForce() {
        autoForceTimer?.invalidate()
        guard autoForceEnabled else { return }
        let secs = Double(max(60, autoForceSeconds))
        autoForceTimer = Timer.scheduledTimer(withTimeInterval: secs, repeats: true) { [weak self] _ in
            Task { @MainActor in
                guard let self, self.autoForceIsDue else { return }
                // La primera vez que consulta sola, avisar: aunque `/usage` sea
                // casi gratis, es una acción automática y no debe sorprender.
                let notifiedKey = "autoForceNotified"
                if !UserDefaults.standard.bool(forKey: notifiedKey) {
                    UserDefaults.standard.set(true, forKey: notifiedKey)
                    Notifier.shared.send(
                        title: "Clawd consulta tu uso solo",
                        body: self.hasFreeSource
                            ? "Tu dato local lleva rato parado (Claude Code cerrado), así que Clawd lo pide con «/usage». No gasta tokens; el interruptor está en el panel."
                            : "Tu plan no publica la cuota gratis, así que Clawd la pide con «/usage» cada tanto. No gasta tokens; el intervalo y el interruptor están en el panel.")
                }
                guard !self.noAccess else { return }
                self.lastAutoForce = Date()
                self.forceRefresh(silent: true) { [weak self] ok in
                    guard let self else { return }
                    if ok {
                        self.autoForceFailures = 0
                    } else {
                        self.autoForceFailures += 1
                        if self.autoForceFailures >= 3 {
                            self.noAccess = true
                            self.autoForceFailures = 0
                            self.say("Claude no responde 🤒  reintentaré en 5 min", seconds: 30)
                            DispatchQueue.main.asyncAfter(deadline: .now() + 300) { [weak self] in
                                self?.noAccess = false
                            }
                        }
                    }
                }
            }
        }
    }

    /// `--demo` recorre todas las actividades en bucle; `--demo=nap` fija una sola.
    /// Sirve para verlas sin esperar a que le den ganas.
    private func startDemo() {
        activityTimer?.invalidate()

        if let arg = CommandLine.arguments.first(where: { $0.hasPrefix("--demo=") }),
           let one = Activity(rawValue: String(arg.dropFirst("--demo=".count))) {
            activity = one
            return
        }

        let all: [Activity] = [.idle, .coffee, .yawn, .dance, .workout, .nap, .apple]
        var i = 0
        activityTimer = Timer.scheduledTimer(withTimeInterval: 6, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.activity = all[i % all.count]
                i += 1
            }
        }
        activity = .idle
    }

    private func applyLaunchAtLogin(_ on: Bool) {
        loginError = nil
        do {
            if on { try SMAppService.mainApp.register() }
            else  { try SMAppService.mainApp.unregister() }
        } catch {
            loginError = error.localizedDescription
            // Si falló, el interruptor debe volver a lo que diga el sistema.
            syncingLogin = true
            launchAtLogin = SMAppService.mainApp.status == .enabled
            syncingLogin = false
        }
    }

    /// Programa la próxima ocurrencia. Los intervalos son largos a propósito:
    /// la gracia es que sorprenda, no que esté haciendo cosas todo el rato.
    private func scheduleActivity() {
        activityTimer?.invalidate()
        guard activitiesEnabled else { return }
        let delay = Double.random(in: 45...150)
        activityTimer = Timer.scheduledTimer(withTimeInterval: delay, repeats: false) { [weak self] _ in
            Task { @MainActor in self?.startActivity() }
        }
    }

    /// Clic sobre Clawd: sonríe. De paso relee, que es gratis e instantáneo.
    func poke() {
        reload(force: true)
        say(["¡hola!", "¡ey!", "aquí sigo", "¿qué tal?", "todo bien por acá",
             "me alegro de verte"].randomElement() ?? "¡hola!", seconds: 2.8)
        startActivity(.smile, forced: true)
    }

    /// Lanza una actividad ahora. `forced` la dispara aunque estén desactivadas.
    func startActivity(_ chosen: Activity? = nil, forced: Bool = false) {
        guard activitiesEnabled || forced else { return }
        let a = chosen ?? Activity.random(night: isNight)
        activity = a
        activityTimer?.invalidate()
        activityTimer = Timer.scheduledTimer(withTimeInterval: a.duration, repeats: false) { [weak self] _ in
            Task { @MainActor in
                self?.activity = .idle
                self?.scheduleActivity()
            }
        }
    }

    private func scheduleTimer() {
        timer?.invalidate()
        let secs = Double(max(2, pollSeconds))
        timer = Timer.scheduledTimer(withTimeInterval: secs, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.reload() }
        }
        timer?.tolerance = secs * 0.2
    }

    /// Lectura local: instantánea y sin costo.
    func reload(announce: Bool = false, force: Bool = false, silent: Bool = false) {
        tick = Date()
        claudeActive = LocalUsage.claudeCodeActive()

        // Si ningún archivo se ha tocado, no hay nada que releer.
        let stamps = LocalUsage.stamps()
        if !force, !announce, usage != nil, stamps == lastStamps { return }
        lastStamps = stamps

        guard let fresh = LocalUsage.best() else {
            if usage == nil { errorMsg = LocalUsage.emptyReason() }
            return
        }
        errorMsg = nil
        let changed = fresh != usage
        let previousWorst = lastWorst
        usage = fresh
        lastWorst = fresh.worst

        if !silent && (announce || (changed && fresh.worst != previousWorst)) {
            say(mood.phrase(seed: fresh.worst &+ Int(fresh.fetchedAt.timeIntervalSince1970) / 97))
            maybeNotify(new: fresh)
        }
    }

    /// Único camino que habla con el servidor (`/usage`), y solo si se pide.
    func forceRefresh(silent: Bool = false, onComplete: ((Bool) -> Void)? = nil) {
        guard !forcing else { onComplete?(false); return }
        forcing = true
        if !silent { say("Preguntándole al servidor… 📡") }
        Task.detached(priority: .utility) {
            let err = ClaudeRunner.forceRefresh()
            await MainActor.run {
                self.forcing = false
                if let err { self.errorMsg = err }
                self.reload(announce: !silent, silent: silent)
                onComplete?(err == nil)
            }
        }
    }

    func say(_ text: String, seconds: Double = 9) {
        bubbleTask?.cancel()
        bubble = text
        let t = DispatchWorkItem { [weak self] in Task { @MainActor in self?.bubble = nil } }
        bubbleTask = t
        DispatchQueue.main.asyncAfter(deadline: .now() + seconds, execute: t)
    }

    /// Notifica solo al cruzar un umbral hacia arriba (50/70/90).
    private func maybeNotify(new: Usage) {
        guard notifyEnabled else { return }
        let step: Int
        switch new.worst {
        case ..<50: step = 0
        case ..<70: step = 1
        case ..<90: step = 2
        default:    step = 3
        }
        let previous = lastNotifiedStep
        lastNotifiedStep = step
        guard step > 0, step > previous, previous >= 0 || step >= 2 else { return }

        let titles = ["", "Vas por la mitad", "Ojo con el consumo", "¡Cuota casi agotada!"]
        let detail = new.limits.filter { $0.percent > 0 }
            .map { "\($0.label.prefix(6)) \($0.percent)%" }.joined(separator: " · ")
        notify(title: "\(mood.face) \(titles[step])",
               body: detail.isEmpty ? "\(new.worst)% usado" : detail)
    }

    private func notify(title: String, body: String) {
        Notifier.shared.send(title: title, body: body)
    }
}

// ─────────────────────────────────────────────────────────────
// MARK: - Utilidades de formato
// ─────────────────────────────────────────────────────────────

enum Fmt {
    static func ago(_ d: Date) -> String {
        let s = Int(max(0, Date().timeIntervalSince(d)))
        if s < 60 { return "hace \(s) s" }
        if s < 3600 { return "hace \(s / 60) min" }
        if s < 86400 { return "hace \(s / 3600) h" }
        return "hace \(s / 86400) d"
    }

    static func reset(_ d: Date?) -> String {
        guard let d else { return "" }
        let f = DateFormatter()
        f.locale = Locale(identifier: "es_CO")
        f.dateFormat = Calendar.current.isDateInToday(d) ? "'hoy a las' h:mm a"
                     : Calendar.current.isDateInTomorrow(d) ? "'mañana a las' h:mm a"
                     : "EEEE d 'a las' h:mm a"
        return f.string(from: d)
    }
}

// ─────────────────────────────────────────────────────────────
// MARK: - Componentes de UI
// ─────────────────────────────────────────────────────────────

/// Punto-anillo diminuto para la leyenda: anillo grueso = exterior (semana).
struct RingKey: View {
    let pct: Int
    let label: String
    var small = false
    var detail: String? = nil

    var body: some View {
        HStack(spacing: 3) {
            Circle()
                .stroke(Mood.from(pct).color, lineWidth: small ? 1.2 : 2.2)
                .frame(width: 8, height: 8)
            Text(label)
        }
        // ponytail: tooltip nativo de macOS en vez de un segundo texto fijo —
        // el detalle en dólares aparece al pasar el mouse, sin ocupar espacio.
        .help(detail ?? "")
    }
}

struct UsageBar: View {
    let limit: Limit

    private var mood: Mood { Mood.from(limit.percent) }
    private var tint: Color { mood.color }

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 5) {
                Text(limit.label).font(.system(size: 11, weight: .medium))
                if limit.isActive {
                    Circle().fill(tint).frame(width: 5, height: 5)
                }
                Spacer()
                if let detail = limit.detail {
                    Text(detail)
                        .font(.system(size: 10, weight: .medium, design: .rounded))
                        .foregroundStyle(.secondary)
                }
                Text("\(limit.percent)%")
                    .font(.system(size: 11, weight: .bold, design: .rounded))
                    .foregroundStyle(mood.textColor)
            }
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    Capsule().fill(Color.primary.opacity(0.10))
                    Capsule()
                        .fill(LinearGradient(colors: [tint.opacity(0.65), tint],
                                             startPoint: .leading, endPoint: .trailing))
                        .frame(width: max(3, geo.size.width * CGFloat(min(limit.percent, 100)) / 100))
                }
            }
            .frame(height: 7)
            if let r = limit.resetsAt {
                Text("se reinicia \(Fmt.reset(r))")
                    .font(.system(size: 9)).foregroundStyle(.secondary)
            }
        }
        .animation(.easeOut(duration: 0.5), value: limit.percent)
    }
}

/// Una capa de píxeles: su rejilla, su color y dónde va dentro del lienzo.
struct PixelLayer {
    let rows: [String]
    let color: Color
    var dx: Int = 0
    var dy: Int = 0
    var opacity: Double = 1
    var shift: CGSize = .zero      // desplazamiento fino, en celdas
}

/// Dibuja capas de píxeles. Va con `Canvas` y no con vistas: son ~180 celdas y
/// además el pixel-art no debe interpolar entre fotogramas.
struct PixelCanvas: View {
    let layers: [PixelLayer]
    let cols: Int
    let rowCount: Int
    let cell: CGFloat

    var body: some View {
        Canvas { ctx, _ in
            for layer in layers {
                ctx.opacity = layer.opacity
                for (r, line) in layer.rows.enumerated() {
                    for (c, ch) in line.enumerated() where ch == "#" {
                        let x = (CGFloat(layer.dx + c) + layer.shift.width) * cell
                        let y = (CGFloat(layer.dy + r) + layer.shift.height) * cell
                        // El +0.5 evita costuras finas entre celdas contiguas.
                        ctx.fill(Path(CGRect(x: x, y: y, width: cell + 0.5, height: cell + 0.5)),
                                 with: .color(layer.color))
                    }
                }
            }
        }
        .frame(width: cell * CGFloat(cols), height: cell * CGFloat(rowCount))
    }
}

/// Sprite pixel-art de Clawd, la mascota de Claude Code.
/// La rejilla sale de `clawd.svg` de la extensión oficial (11 × 8 celdas, #D97757).
enum Clawd {
    static let cols = 11, rows = 8
    static let brand = Color(red: 0xD9/255, green: 0x77/255, blue: 0x57/255)
    static let brandNS = NSColor(red: 0xD9/255, green: 0x77/255, blue: 0x57/255, alpha: 1)

    /// Cuerpo sin los bracitos: esos van en capas aparte para poder moverlos solos.
    static let body: [String] = [
        ".#########.",
        ".#########.",
        ".#.#####.#.",   // ojos en las columnas 2 y 8
        ".#########.",
        ".#########.",
        ".#########.",
        ".#.#...#.#.",   // patas en las columnas 1, 3, 7 y 9
        ".#.#...#.#.",
    ]
    static let eyeCols = [2, 8]

    // ── Accesorios ───────────────────────────────────────────
    static let capBody  = ["...........", "....#####..", "..######...", "..........."]
    static let capTrim  = ["........##.", "...........", "...........", ".#########."]
    static let mugBody  = ["###.", "####", "###."]
    static let mugCoffee = ["###."]
    static let apple    = ["..#.", ".###", "####", ".##."]
    static let appleStem = ["..#."]
    static let zed      = ["###", "..#", ".#.", "###"]

    static let capColor   = Color(red: 0x4C/255, green: 0x63/255, blue: 0xC9/255)
    static let capTrimCol = Color(red: 0xED/255, green: 0xED/255, blue: 0xF0/255)
    static let mugColor   = Color(red: 0xEF/255, green: 0xEA/255, blue: 0xE3/255)
    static let coffeeCol  = Color(red: 0x4A/255, green: 0x2C/255, blue: 0x17/255)
    static let steamCol   = Color(red: 0xD8/255, green: 0xDE/255, blue: 0xE6/255)
    static let appleCol   = Color(red: 0xD9/255, green: 0x3A/255, blue: 0x3A/255)
    static let stemCol    = Color(red: 0x6B/255, green: 0x44/255, blue: 0x23/255)
    static let zedCol     = Color(red: 0xC3/255, green: 0xCD/255, blue: 0xDB/255)

    static let thermometer = [".#", ".#", ".#", "##", "##"]
    static let thermCol    = Color(red: 0xED/255, green: 0x4C/255, blue: 0x4C/255)
    static let sickColor   = Color(red: 0x68/255, green: 0xC2/255, blue: 0x7A/255)

    static let cane      = [".#", ".#", ".#", ".#", "##"]
    static let caneCol   = Color(red: 0xC8/255, green: 0xA8/255, blue: 0x78/255)
    static let oldColor  = Color(red: 0xA0/255, green: 0x98/255, blue: 0x90/255)
    static let beard     = ["#####", "#####", "#####"]
    static let beardCol  = Color.white

    /// Rejilla del cuerpo con ojos, boca y patas según el estado.
    static func bodyGrid(eyes: Eyes, mouth: Int, legLift: Int) -> [[Bool]] {
        var g = body.map { $0.map { $0 == "#" } }

        switch eyes {
        case .open:   break
        case .closed: for c in eyeCols { g[2][c] = true }
        case .wide:   for c in eyeCols { g[1][c] = false }
        case .happy:
            // Ojos entornados: el hueco se ensancha hacia dentro. Se probó el
            // chevron ^^, pero a 8 px se deshace en puntos sueltos, y llevarlo
            // a las columnas del borde le muerde la silueta a la cabeza.
            g[2][2] = false; g[2][3] = false
            g[2][7] = false; g[2][8] = false
        }

        switch mouth {
        case 1: g[4][5] = false
        case 2: for c in 4...6 { g[4][c] = false }
        case 3: for c in 4...6 { g[4][c] = false; g[5][c] = false }
        case 4:
            // Sonrisa ∪ : las puntas suben, el centro baja.
            g[4][3] = false; g[4][7] = false
            for c in 4...6 { g[5][c] = false }
        case 5:
            // Mueca triste ∩ : las puntas bajan, el centro sube.
            g[5][3] = false; g[5][7] = false
            for c in 4...6 { g[4][c] = false }
        default: break
        }

        if legLift != 0 {
            for c in (legLift > 0 ? [1, 7] : [3, 9]) { g[7][c] = false }
        }
        return g
    }

    enum Eyes { case open, closed, wide, happy }

    static func asRows(_ g: [[Bool]]) -> [String] {
        g.map { String($0.map { $0 ? "#" : "." }) }
    }

    /// Imagen para la barra de menús (NSImage, origen abajo-izquierda).
    private static var cache: [String: NSImage] = [:]
    static func menuBarImage(color: NSColor, night: Bool, cell: CGFloat = 2) -> NSImage {
        let key = "\(color.description)-\(night)-\(cell)"
        if let c = cache[key] { return c }

        let g = bodyGrid(eyes: .open, mouth: 0, legLift: 0)
        var strokes: [(String, NSColor, Int, Int)] = []
        // Brazos, que en el cuerpo van aparte
        strokes.append(("#", color, 0, 2)); strokes.append(("#", color, 0, 3))
        strokes.append(("#", color, 10, 2)); strokes.append(("#", color, 10, 3))

        let totalRows = night ? rows + 3 : rows
        let yShift = night ? 3 : 0
        let img = NSImage(size: NSSize(width: cell * CGFloat(cols), height: cell * CGFloat(totalRows)))
        img.lockFocus()

        func put(_ c: Int, _ r: Int, _ col: NSColor) {
            col.setFill()
            NSRect(x: CGFloat(c) * cell,
                   y: CGFloat(totalRows - 1 - r) * cell,
                   width: cell, height: cell).fill()
        }
        if night {
            for (r, line) in capBody.enumerated() {
                for (c, ch) in line.enumerated() where ch == "#" { put(c, r, NSColor(capColor)) }
            }
            for (r, line) in capTrim.enumerated() {
                for (c, ch) in line.enumerated() where ch == "#" { put(c, r, NSColor(capTrimCol)) }
            }
        }
        for (r, row) in g.enumerated() {
            for (c, on) in row.enumerated() where on { put(c, r + yShift, color) }
        }
        for (_, col, c, r) in strokes { put(c, r + yShift, col) }

        img.unlockFocus()
        cache[key] = img
        return img
    }
}

/// Clawd animado. En reposo solo flota y parpadea; de vez en cuando le da por
/// hacer algo (café, siesta, baile…) y de noche se pone el gorrito.
struct ClawdView: View {
    let mood: Mood
    let activity: Activity
    let night: Bool
    var clawdWidth: CGFloat = 44
    var tinted = false
    var sick = false
    var old  = false

    // Lienzo: deja sitio arriba para el gorrito y a la derecha para los accesorios.
    private static let canvasCols = 15, canvasRows = 12
    private static let clawdDX = 2, clawdDY = 4
    private static let propDX = 10

    @State private var blinking = false
    @State private var beat = 0
    @State private var float = false

    /// El vaivén, a saltos y no interpolado.
    ///
    /// Antes era `withAnimation(.easeInOut(1.7)).repeatForever`, y ahí estaba
    /// **todo** el consumo de la app: una animación continua repinta a la
    /// cadencia de la pantalla — 120 Hz en un Mac con ProMotion — y eso costaba
    /// un 12 % de un núcleo con Clawd quieto. Medido apagando sospechosos de uno
    /// en uno: no era el lienzo de píxeles (rasterizarlo con `drawingGroup` no
    /// cambió nada), ni el material del plato, ni su sombra, ni el spinner. Era
    /// la cadencia y solo la cadencia, y no baja con menos fotogramas: a 30 fps
    /// y a 15 fps costaba lo mismo, ~3,8 %. Cualquier movimiento continuo tiene
    /// ese suelo.
    ///
    /// Así que se mueve a saltos: dos posiciones, un cambio cada 0,9 s. Sale a
    /// 0,0 % medido, y de paso es como respiran los sprites de verdad — el
    /// pixel-art nunca interpoló entre fotogramas.
    private let floatTimer = Timer.publish(every: 0.9, on: .main, in: .common).autoconnect()
    private let beatTimer = Timer.publish(every: 0.22, on: .main, in: .common).autoconnect()
    private let blinkTimer = Timer.publish(every: 3.4, on: .main, in: .common).autoconnect()

    private var cell: CGFloat { clawdWidth / CGFloat(Clawd.cols) }
    private var skin: Color { sick ? Clawd.sickColor : old ? Clawd.oldColor : tinted ? mood.color : Clawd.brand }

    // ── Estado de la cara y el cuerpo según la actividad ──────
    private var sipping: Bool { beat % 9 >= 6 }
    private var biting: Bool { beat % 8 >= 6 }

    private var eyes: Clawd.Eyes {
        if sick { return .open }
        if blinking { return .closed }
        switch activity {
        case .nap, .yawn:   return .closed
        case .smile:        return .happy       // ojitos ^^
        case .workout:      return .wide
        default:
            return (mood == .alert || mood == .panic) ? .wide : .open
        }
    }

    private var mouth: Int {
        if sick || old { return 5 }
        switch activity {
        case .yawn:    return 3
        case .smile:   return 4      // sonrisa curva
        case .dance:   return 1
        case .workout: return 2
        case .coffee:  return sipping ? 1 : 0
        case .apple:   return biting ? 2 : 0
        case .nap:     return 1
        case .idle:
            switch mood {
            case .ok: return 1
            case .alert: return 2
            case .panic: return 3
            default: return 0
            }
        }
    }

    private var legLift: Int {
        activity == .dance ? (beat % 2 == 0 ? 1 : -1) : 0
    }

    private var tilt: Double {
        switch activity {
        case .coffee: return sipping ? 9 : 0
        case .dance:  return beat % 2 == 0 ? -11 : 11
        default:      return 0
        }
    }

    /// Desplazamiento del cuerpo, en celdas.
    private var bodyShift: CGSize {
        switch activity {
        case .workout: return CGSize(width: 0, height: beat % 2 == 0 ? 0 : 1.1)
        case .dance:   return CGSize(width: beat % 2 == 0 ? -0.5 : 0.5, height: 0)
        // Un saltito de alegría al principio y ya: nada de sacudidas.
        case .smile:   return CGSize(width: 0, height: beat < 3 ? -0.5 : 0)
        case .nap:     return CGSize(width: 0, height: 0.8)
        default:       return .zero
        }
    }

    private var stretch: CGFloat { activity == .yawn ? 1.14 : activity == .smile ? 1.03 : 1 }

    /// Altura de cada bracito, en celdas (negativo = arriba).
    private func armShift(left: Bool) -> CGFloat {
        switch activity {
        case .dance:   return (left == (beat % 2 == 0)) ? -1 : 0.3
        case .smile:   return beat < 3 ? -0.6 : -0.2       // bracitos apenas alzados
        case .workout: return beat % 2 == 0 ? -1.2 : 0.3
        case .coffee:  return left ? 0 : -0.8
        case .apple:   return left ? 0 : -0.8
        case .nap:     return 0.5
        default:       return 0
        }
    }

    // ── Capas ────────────────────────────────────────────────
    private var clawdLayers: [PixelLayer] {
        let g = Clawd.bodyGrid(eyes: eyes, mouth: mouth, legLift: legLift)
        var out: [PixelLayer] = [
            PixelLayer(rows: Clawd.asRows(g), color: skin,
                       dx: Self.clawdDX, dy: Self.clawdDY, shift: bodyShift)
        ]
        for left in [true, false] {
            let dx = Self.clawdDX + (left ? 0 : Clawd.cols - 1)
            out.append(PixelLayer(rows: ["#", "#"], color: skin,
                                  dx: dx, dy: Self.clawdDY + 2,
                                  shift: CGSize(width: bodyShift.width,
                                                height: bodyShift.height + armShift(left: left))))
        }
        return out
    }

    private var propLayers: [PixelLayer] {
        switch activity {
        case .coffee:
            let steamCol = beat % 2 == 0 ? "#.." : ".#."
            return [
                PixelLayer(rows: [steamCol], color: Clawd.steamCol, dx: Self.propDX, dy: 4,
                           opacity: 0.85),
                PixelLayer(rows: Clawd.mugCoffee, color: Clawd.coffeeCol, dx: Self.propDX, dy: 6),
                PixelLayer(rows: Clawd.mugBody, color: Clawd.mugColor, dx: Self.propDX, dy: 7),
            ]
        case .apple:
            let bites = min(3, beat / 8)
            var rows = Clawd.apple
            if bites > 0 {
                for r in 1...2 {
                    var line = Array(rows[r])
                    for k in 0..<bites where line.count - 1 - k >= 0 {
                        line[line.count - 1 - k] = "."
                    }
                    rows[r] = String(line)
                }
            }
            return [
                PixelLayer(rows: Clawd.appleStem, color: Clawd.stemCol, dx: Self.propDX + 1, dy: 5),
                PixelLayer(rows: rows, color: Clawd.appleCol, dx: Self.propDX + 1, dy: 6),
            ]
        case .nap:
            let t = Double(beat % 12) / 12.0
            return [
                PixelLayer(rows: Clawd.zed, color: Clawd.zedCol, dx: Self.propDX, dy: 5,
                           opacity: max(0, 1 - t * 0.8),
                           shift: CGSize(width: t * 1.0, height: -t * 2.5)),
                PixelLayer(rows: Clawd.zed, color: Clawd.zedCol, dx: Self.propDX - 1, dy: 7,
                           opacity: max(0, 0.85 - t * 0.9),
                           shift: CGSize(width: t * 0.7, height: -t * 1.8)),
            ]
        default:
            if old {
                return [PixelLayer(rows: Clawd.cane, color: Clawd.caneCol,
                                   dx: Self.propDX, dy: Self.clawdDY + 3)]
            }
            return []
        }
    }

    private var capLayers: [PixelLayer] {
        guard night else { return [] }
        return [
            PixelLayer(rows: Clawd.capBody, color: Clawd.capColor,
                       dx: Self.clawdDX, dy: Self.clawdDY - 3, shift: bodyShift),
            PixelLayer(rows: Clawd.capTrim, color: Clawd.capTrimCol,
                       dx: Self.clawdDX, dy: Self.clawdDY - 3, shift: bodyShift),
        ]
    }

    var body: some View {
        PixelCanvas(layers: clawdLayers + capLayers + propLayers,
                    cols: Self.canvasCols, rowCount: Self.canvasRows, cell: cell)
            .scaleEffect(x: 1, y: stretch, anchor: .bottom)
            .rotationEffect(.degrees(tilt))
            // Centra a Clawd (no el lienzo) dentro del anillo.
            .offset(x: cell * 0.5, y: -cell * 1.5)
            .offset(y: float ? -cell * 0.3 : cell * 0.3)
            .animation(.easeInOut(duration: 0.18), value: beat)
            .onReceive(floatTimer) { _ in float.toggle() }
            .onReceive(beatTimer) { _ in
                if activity != .idle { beat &+= 1 } else if beat != 0 { beat = 0 }
            }
            .onReceive(blinkTimer) { _ in
                guard mood != .broken, activity != .nap, activity != .smile else { return }
                blinking = true
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.14) { blinking = false }
            }
    }
}
/// Un anillo de progreso: pista tenue + arco de color.
struct ProgressRing: View {
    let pct: Int
    let lineWidth: CGFloat
    var inset: CGFloat = 0

    private var color: Color { Mood.from(pct).color }

    var body: some View {
        ZStack {
            Circle().stroke(Color.primary.opacity(0.13), lineWidth: lineWidth)
            Circle()
                .trim(from: 0, to: CGFloat(min(pct, 100)) / 100)
                .stroke(color, style: StrokeStyle(lineWidth: lineWidth, lineCap: .round))
                .rotationEffect(.degrees(-90))
                .animation(.easeOut(duration: 0.7), value: pct)
        }
        .padding(inset)
    }
}

/// Clawd entre dos anillos concéntricos: el exterior es la semana, el interior la sesión.
struct MascotView: View {
    let mood: Mood
    let weekPct: Int
    let sessionPct: Int
    let busy: Bool
    var activity: Activity = .idle
    var night = false
    var size: CGFloat = 64
    var showRing = true
    var backdrop = false
    var tinted = false
    var sick = false
    var old  = false
    /// false cuando el plan solo separa una dimensión (Team/Enterprise): un
    /// solo anillo, del ancho del exterior, en vez de uno relleno y otro vacío.
    var hasSecondary = true

    @State private var spin = 0.0

    private var outerWidth: CGFloat { size * 0.072 }
    private var innerWidth: CGFloat { size * 0.056 }
    private var innerInset: CGFloat { size * 0.105 }

    var body: some View {
        ZStack {
            if backdrop {
                Circle()
                    .fill(.ultraThinMaterial)
                    .overlay(Circle().stroke(Color.primary.opacity(0.12), lineWidth: 0.5))
                    .shadow(color: .black.opacity(0.25), radius: 8, y: 3)
                    .padding(size * 0.028)
            }
            if showRing {
                if hasSecondary {
                    ProgressRing(pct: weekPct, lineWidth: outerWidth)
                    ProgressRing(pct: sessionPct, lineWidth: innerWidth, inset: innerInset)
                } else {
                    ProgressRing(pct: sessionPct, lineWidth: outerWidth)
                }
            }
            // Clawd tiene que caber DENTRO del anillo interior, de ahí el 0.48.
            ClawdView(mood: mood, activity: activity, night: night,
                      clawdWidth: size * 0.48, tinted: tinted, sick: sick, old: old)
        }
        .frame(width: size, height: size)
        .onAppear {
            withAnimation(.linear(duration: 0.9).repeatForever(autoreverses: false)) { spin = 360 }
        }
    }
}

struct Bubble: View {
    let text: String
    var body: some View {
        VStack(spacing: 0) {
            Text(text)
                .font(.system(size: 11, weight: .medium))
                .multilineTextAlignment(.center)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.horizontal, 10).padding(.vertical, 7)
                .background(
                    RoundedRectangle(cornerRadius: 11, style: .continuous)
                        .fill(.regularMaterial)
                        .shadow(color: .black.opacity(0.18), radius: 6, y: 2))
            Triangle().fill(.regularMaterial).frame(width: 12, height: 7)
        }
        .frame(maxWidth: 170)
    }
}

struct Triangle: Shape {
    func path(in r: CGRect) -> Path {
        var p = Path()
        p.move(to: CGPoint(x: r.minX, y: r.minY))
        p.addLine(to: CGPoint(x: r.maxX, y: r.minY))
        p.addLine(to: CGPoint(x: r.midX, y: r.maxY))
        p.closeSubpath()
        return p
    }
}

// ─────────────────────────────────────────────────────────────
// MARK: - Panel de la barra de menús
// ─────────────────────────────────────────────────────────────

struct PanelView: View {
    @ObservedObject var store = PetStore.shared
    @ObservedObject var notifier = Notifier.shared

    private let pollOptions: [(Int, String)] = [
        (5, "cada 5 s"), (10, "cada 10 s"), (30, "cada 30 s"),
        (60, "cada minuto"), (300, "cada 5 min"),
    ]

    /// El mínimo es un minuto a propósito: cada consulta arranca el CLI de
    /// Claude Code, que cuesta ~1,3 s de CPU y un pico de 580 MB de RAM. A 30 s
    /// eso serían dos picos por minuto para un dato que casi no se mueve.
    private let autoForceOptions: [(Int, String)] = [
        (60, "cada minuto"), (120, "cada 2 min"), (300, "cada 5 min"),
    ]

    /// Lo que cuesta de verdad, medido en esta máquina: 1,32 s de CPU por
    /// consulta. Se enseña para que la decisión no sea a ciegas. En Pro/Max el
    /// intervalo del selector no manda: como solo dispara con el dato viejo, dos
    /// consultas no pueden caer más juntas que `staleAfter`.
    private var autoForceCost: String {
        let secs = Double(max(60, store.autoForceSeconds))
        let real = store.hasFreeSource ? max(secs, Usage.staleAfter) : secs
        return String(format: "~%.1f %% de un núcleo", 1.32 / real * 100)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 13) {

            HStack(alignment: .center, spacing: 12) {
                MascotView(mood: store.mood,
                           weekPct: store.usage?.weekPct ?? 0,
                           sessionPct: store.usage?.sessionPct ?? 0,
                           busy: store.forcing,
                           activity: store.activity, night: store.isNight,
                           size: 66, tinted: store.tintClawd,
                           sick: store.noAccess,
                           old: store.dataLooksStale || store.demoOld,
                           hasSecondary: store.usage?.hasSecondary ?? true)
                    .contentShape(Circle())
                    .onTapGesture { store.poke() }
                VStack(alignment: .leading, spacing: 3) {
                    Text("Claude Pet")
                        .font(.system(size: 14, weight: .bold, design: .rounded))
                    Text(store.bubble ?? store.mood.phrase(seed: store.usage?.worst ?? 0))
                        .font(.system(size: 11)).foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                    HStack(spacing: 4) {
                        if store.usage?.hasSecondary ?? true {
                            RingKey(pct: store.usage?.weekPct ?? 0, label: store.usage?.weekLabel ?? "semana")
                            Text("·").foregroundStyle(.quaternary)
                            RingKey(pct: store.usage?.sessionPct ?? 0, label: store.usage?.sessionLabel ?? "sesión", small: true)
                        } else {
                            // Una sola bolsa (Team/Enterprise): una barra, no dos ventanas inventadas.
                            // El detalle en dólares va de tooltip, no ocupa espacio fijo.
                            RingKey(pct: store.usage?.sessionPct ?? 0, label: store.usage?.sessionLabel ?? "uso",
                                    detail: store.usage?.sessionDetail)
                        }
                    }
                    .font(.system(size: 9))
                    .foregroundStyle(.secondary)
                }
                Spacer(minLength: 0)
            }

            if let err = store.loginError {
                Text("No pude cambiar el arranque automático: \(err)")
                    .font(.system(size: 9)).foregroundStyle(Mood.alert.textColor)
                    .fixedSize(horizontal: false, vertical: true)
            }

            if let err = store.errorMsg {
                Text(err)
                    .font(.system(size: 10)).foregroundStyle(.orange)
                    .lineLimit(4).padding(7)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(RoundedRectangle(cornerRadius: 7).fill(Color.orange.opacity(0.10)))
            }

            if let u = store.usage {
                VStack(spacing: 11) {
                    if let s = u.session { UsageBar(limit: s) }
                    if let w = u.weekly  { UsageBar(limit: w) }
                    ForEach(u.others) { UsageBar(limit: $0) }
                }

                // Frescura del dato — clave, porque el caché solo se actualiza al usar Claude Code.
                HStack(spacing: 5) {
                    Image(systemName: store.dataLooksStale ? "clock.badge.exclamationmark" : "clock")
                    Text("dato de \(Fmt.ago(u.fetchedAt))")
                    Text("·").foregroundStyle(.tertiary)
                    Text(u.source).foregroundStyle(.tertiary)
                }
                .font(.system(size: 9))
                .foregroundStyle(store.dataLooksStale ? Mood.alert.textColor : .secondary)
                .id(store.tick)
            }

            Divider()

            VStack(alignment: .leading, spacing: 9) {
                HStack {
                    Text("Releer archivo local").font(.system(size: 11))
                    Picker("", selection: $store.pollSeconds) {
                        ForEach(pollOptions, id: \.0) { Text($0.1).tag($0.0) }
                    }
                    .labelsHidden().controlSize(.small)
                }
                Toggle("Abrir al iniciar sesión", isOn: $store.launchAtLogin)
                Toggle("Mascota en el escritorio", isOn: $store.petVisible)
                Toggle("Avisarme al cruzar 50/70/90 %", isOn: $store.notifyEnabled)
                if store.notifyEnabled && notifier.denied {
                    HStack(spacing: 4) {
                        Image(systemName: "bell.slash")
                        Text("Bloqueadas por el sistema.")
                        Button("Abrir Ajustes") { notifier.openSettings() }
                            .buttonStyle(.link)
                    }
                    .font(.system(size: 9))
                    .foregroundStyle(Mood.alert.textColor)
                }
                Toggle("Clawd cambia de color con el humor", isOn: $store.tintClawd)
                Toggle("Actividades: café, siesta, baile…", isOn: $store.activitiesEnabled)
                HStack(spacing: 10) {
                    Button("Que haga algo ahora 🎲") { store.startActivity(forced: true) }
                        .buttonStyle(.link).font(.system(size: 10))
                    if store.isNight {
                        Text("🌙 modo noche").font(.system(size: 9)).foregroundStyle(.tertiary)
                    }
                }
                if store.petVisible {
                    Button("Traer a Clawd a esta pantalla") {
                        store.onRecenterPet?()
                    }
                    .buttonStyle(.link).font(.system(size: 10))
                }
            }
            .toggleStyle(.switch).controlSize(.mini).font(.system(size: 11))

            if store.dataLooksStale, store.usage?.source != "statusLine" {
                Label("El caché solo se refresca cuando usas Claude Code. Para datos al "
                      + "instante instala el hook: ./install-statusline.sh",
                      systemImage: "bolt.badge.clock")
                    .font(.system(size: 9))
                    .foregroundStyle(Mood.alert.textColor)
                    .fixedSize(horizontal: false, vertical: true)
            } else {
                Label("Leer el archivo local no consume nada de tu cuota.",
                      systemImage: "leaf.fill")
                    .font(.system(size: 9)).foregroundStyle(Mood.chill.textColor)
            }

            Divider()

            HStack(spacing: 8) {
                Button {
                    store.forceRefresh()
                } label: {
                    Label(store.forcing ? "Consultando…" : "Forzar (/usage)",
                          systemImage: "antenna.radiowaves.left.and.right")
                }
                .disabled(store.forcing).controlSize(.small)
                .help("Ejecuta `claude -p \"/usage\"` para traer cifras frescas del servidor. No gasta tokens: el CLI lo resuelve sin un turno del modelo (medido con --output-format json: num_turns 0, total_cost_usd 0).")

                Spacer()

                Button("Salir") { NSApplication.shared.terminate(nil) }
                    .controlSize(.small)
            }

            // El único modo de no quedarse mirando un dato viejo es pedirlo otra
            // vez: en Team/Enterprise porque no hay ninguna fuente que se refresque
            // sola, y en Pro/Max porque la que hay (`rate_limits`, vía el hook) se
            // para en seco al cerrar Claude Code. `/usage` no gasta tokens, pero
            // cada consulta arranca el CLI entero: de ahí el interruptor.
            Toggle("Consultar /usage sola (no gasta tokens)", isOn: $store.autoForceEnabled)
                .toggleStyle(.switch).controlSize(.mini).font(.system(size: 10))
            if store.autoForceEnabled {
                if store.hasFreeSource {
                    // Sin selector a propósito: aquí solo dispara con el dato
                    // viejo, así que el intervalo real lo fija `staleAfter`.
                    Text("Solo con Claude Code cerrado, cuando el dato pasa de 15 min. "
                         + autoForceCost + ".")
                        .font(.system(size: 9)).foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                } else {
                    HStack {
                        Picker("", selection: $store.autoForceSeconds) {
                            ForEach(autoForceOptions, id: \.0) { Text($0.1).tag($0.0) }
                        }
                        .labelsHidden().controlSize(.small)
                        Text(autoForceCost).font(.system(size: 9)).foregroundStyle(.secondary)
                    }
                }
            }
        }
        .padding(15)
        .frame(width: 306)
        .animation(.easeInOut(duration: 0.25), value: store.bubble)
    }
}

// ─────────────────────────────────────────────────────────────
// MARK: - Mascota flotante en el escritorio
// ─────────────────────────────────────────────────────────────

struct DesktopPetView: View {
    @ObservedObject var store = PetStore.shared
    @State private var hovering = false

    private var stale: Bool { store.dataLooksStale }

    /// Menú de clic derecho. Existe porque esconder la mascota es lo que más se
    /// busca, y tenerlo solo dentro del panel de la barra de menús no se encuentra.
    @ViewBuilder private var petMenu: some View {
        Button("Ocultar del escritorio") { store.petVisible = false }
        Text("Clawd se queda en la barra de menús")

        Divider()

        Button("Salúdalo 🙂") { store.poke() }
        Button("Actualizar ahora") { store.reload(announce: true, force: true) }
        Button("Que haga algo 🎲") { store.startActivity(forced: true) }
        Toggle("Actividades automáticas", isOn: $store.activitiesEnabled)

        Divider()

        Button("Traer a esta pantalla") { store.onRecenterPet?() }

        Divider()

        Button("Salir de Claude Pet") { NSApplication.shared.terminate(nil) }
    }

    private var hoverText: String {
        guard let u = store.usage else { return "Sin datos todavía" }
        var parts = ["\(u.session != nil ? "Sesión" : u.sessionLabel) \(u.sessionPct)%"]
        if u.hasSecondary { parts.append("\(u.weekly != nil ? "Semana" : u.weekLabel) \(u.weekPct)%") }
        let age = "\(Fmt.ago(u.fetchedAt))"
        var text = parts.joined(separator: " · ")
        if !u.hasSecondary, let detail = u.sessionDetail { text += "\n\(detail)" }
        return text + "\n"
             + (store.dataLooksStale ? "⚠︎ dato de \(age), puede estar viejo" : age)
    }

    var body: some View {
        VStack(spacing: 0) {
            ZStack {
                if let b = store.bubble { Bubble(text: b) }
                else if hovering { Bubble(text: hoverText) }
            }
            .frame(height: 66, alignment: .bottom)

            MascotView(mood: store.mood,
                       weekPct: store.usage?.weekPct ?? 0,
                       sessionPct: store.usage?.sessionPct ?? 0,
                       busy: store.forcing,
                       activity: store.activity, night: store.isNight,
                       size: 96, backdrop: true, tinted: store.tintClawd,
                       sick: store.noAccess,
                       old: store.dataLooksStale || store.demoOld,
                       hasSecondary: store.usage?.hasSecondary ?? true)
                .contentShape(Circle())
                .onTapGesture { store.poke() }
                .help("Clic: saludar · Clic derecho: opciones · Arrastra para mover")
                .contextMenu { petMenu }

            HStack(spacing: 3) {
                if stale {
                    Image(systemName: "clock.badge.exclamationmark")
                        .font(.system(size: 8, weight: .bold))
                }
                Text(store.usage?.compactText ?? "0/0%")
                    .font(.system(size: 11, weight: .bold, design: .rounded))
            }
            .foregroundStyle(.white)
            .padding(.horizontal, 8).padding(.vertical, 2.5)
            .background(
                Capsule()
                    .fill(stale ? Mood.broken.deep : store.mood.deep)
                    .overlay(Capsule().stroke(.white.opacity(0.28), lineWidth: 0.5))
            )
            .shadow(color: .black.opacity(0.3), radius: 4, y: 1)
            .offset(y: -2)
        }
        .padding(.horizontal, 6)
        .padding(.bottom, 4)
        .frame(width: PetPanel.petSize.width, height: PetPanel.petSize.height)
        .onHover { hovering = $0 }
        .animation(.spring(response: 0.35, dampingFraction: 0.7), value: store.bubble)
        .animation(.easeInOut(duration: 0.2), value: hovering)
    }
}

final class PetPanel: NSPanel {
    static let petSize = CGSize(width: 200, height: 192)

    init() {
        super.init(contentRect: NSRect(origin: .zero, size: Self.petSize),
                   styleMask: [.borderless, .nonactivatingPanel],
                   backing: .buffered, defer: false)
        isOpaque = false
        backgroundColor = .clear
        hasShadow = false
        level = .floating
        isMovableByWindowBackground = true
        hidesOnDeactivate = false
        collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .stationary]

        let host = NSHostingView(rootView: DesktopPetView())
        host.wantsLayer = true
        host.layer?.backgroundColor = .clear
        contentView = host

        setFrameAutosaveName("ClaudePetWindow")
        // El autosave puede restaurar un tamaño viejo o una posición en una pantalla
        // que ya no está conectada; forzamos el tamaño y validamos la posición.
        setContentSize(Self.petSize)
        if frame.origin == .zero || !isOnAnyScreen { recenter() }
    }

    /// ¿La ventana queda dentro de alguna pantalla conectada?
    private var isOnAnyScreen: Bool {
        NSScreen.screens.contains { $0.visibleFrame.intersects(frame) }
    }

    /// La lleva abajo a la derecha de la pantalla principal.
    func recenter() {
        guard let vis = NSScreen.main?.visibleFrame else { return }
        setContentSize(Self.petSize)
        setFrameOrigin(NSPoint(x: vis.maxX - Self.petSize.width - 24,
                               y: vis.minY + 24))
    }

    /// Con `.nonactivatingPanel` puede volverse key sin activar la app, que es
    /// lo que necesita el menú contextual para aparecer.
    override var canBecomeKey: Bool { true }
}

// ─────────────────────────────────────────────────────────────
// MARK: - App
// ─────────────────────────────────────────────────────────────

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var panel: PetPanel?

    func applicationDidFinishLaunching(_ n: Notification) {
        if CommandLine.arguments.contains("--dump") { Self.dumpAndExit() }
        if CommandLine.arguments.contains("--dump-raw") { Self.dumpRawAndExit() }
        if CommandLine.arguments.contains("--login-on")  { Self.setLoginAndExit(true) }
        if CommandLine.arguments.contains("--login-off") { Self.setLoginAndExit(false) }
        NSApp.setActivationPolicy(.accessory)
        let store = PetStore.shared
        store.onPetVisibilityChange = { [weak self] v in
            Task { @MainActor in self?.setPet(v) }
        }
        store.onRecenterPet = { [weak self] in
            Task { @MainActor in
                self?.setPet(true)
                self?.panel?.recenter()
            }
        }
        setPet(store.petVisible)
        Notifier.shared.refreshStatus()
        store.start()
    }

    static func setLoginAndExit(_ on: Bool) -> Never {
        do {
            if on { try SMAppService.mainApp.register() }
            else  { try SMAppService.mainApp.unregister() }
            print(on ? "✅ Arrancará al iniciar sesión." : "✅ Ya no arranca al iniciar sesión.")
        } catch {
            print("❌ \(error.localizedDescription)")
        }
        exit(0)
    }

    static func loginStatusText() -> String {
        switch SMAppService.mainApp.status {
        case .enabled:          return "activado"
        case .notRegistered:    return "no activado"
        case .requiresApproval: return "pendiente de aprobación en Ajustes → Ítems de inicio"
        case .notFound:         return "no encontrado"
        @unknown default:       return "desconocido"
        }
    }

    /// Vuelca el bloque de cuota tal cual, quitando lo que identifica a la cuenta.
    /// Sirve para diagnosticar planes que no puedo probar (Team, Enterprise) sin
    /// pedirle a nadie que comparta su archivo entero.
    static func dumpRawAndExit() -> Never {
        guard let data = try? Data(contentsOf: LocalUsage.claudeJSON),
              let root = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let cached = root["cachedUsageUtilization"] as? [String: Any]
        else {
            print("No encontré cachedUsageUtilization en \(LocalUsage.claudeJSON.path)")
            exit(1)
        }

        /// Además del nombre de la clave, se miran los VALORES: un identificador
        /// puede vivir bajo una clave de aspecto inocente (`owner`, `name`…). Es
        /// heurístico, no una garantía — por eso el usuario revisa antes de pegar.
        func looksSensitive(_ s: String) -> Bool {
            if s.contains("@"), s.contains(".") { return true }   // correo
            let uuid = "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
            if s.range(of: uuid, options: .regularExpression) != nil { return true }
            // token/opaco: 24+ caracteres seguidos sin espacios ni puntuación
            // (las fechas ISO llevan «:» y «-» separados, así que no caen aquí).
            if s.count >= 24, s.range(of: "^[A-Za-z0-9_-]{24,}$", options: .regularExpression) != nil { return true }
            return false
        }

        /// Fuera cualquier cosa que huela a identificador o credencial.
        func redact(_ value: Any) -> Any {
            if let s = value as? String { return looksSensitive(s) ? "«omitido»" : s }
            if var dict = value as? [String: Any] {
                for key in dict.keys {
                    let k = key.lowercased()
                    if ["uuid", "id", "email", "token", "key", "secret", "account", "org"]
                        .contains(where: { k.contains($0) }) {
                        dict[key] = "«omitido»"
                    } else {
                        dict[key] = redact(dict[key]!)
                    }
                }
                return dict
            }
            if let arr = value as? [Any] { return arr.map(redact) }
            return value
        }

        var out: [String: Any] = ["utilization": redact(cached["utilization"] ?? [:])]
        out["tier"] = (root["oauthAccount"] as? [String: Any])?["organizationRateLimitTier"] ?? "?"
        out["hasOAuthAccount"] = root["oauthAccount"] != nil

        if let json = try? JSONSerialization.data(withJSONObject: out,
                                                  options: [.prettyPrinted, .sortedKeys]),
           let text = String(data: json, encoding: .utf8) {
            print(text)
        }
        exit(0)
    }

    /// El `statusLine` que manda no es siempre el del usuario: las settings del
    /// proyecto (`.claude/settings.json`, y la `.local` por encima) ganan sobre
    /// `~/.claude/settings.json`, que es donde escriben nuestros instaladores.
    /// Si en el directorio actual hay uno ajeno, el hook no corre aquí por mucho
    /// que el instalador dijera «✅ instalado», y la mascota se queda sin datos
    /// frescos sin que nada explique por qué. Devuelve la capa y el comando.
    static func statusLineOverride() -> (layer: String, command: String)? {
        func command(at url: URL) -> String? {
            guard let d = try? Data(contentsOf: url),
                  let root = try? JSONSerialization.jsonObject(with: d) as? [String: Any],
                  let line = root["statusLine"] as? [String: Any],
                  let cmd = line["command"] as? String else { return nil }
            return cmd
        }
        let cwd = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
        // De más a menos prioridad. Manda la PRIMERA capa que defina un
        // statusLine, sea de quien sea: si esa es la nuestra no hay conflicto,
        // y las de debajo dan igual porque ya no se leen.
        for name in ["settings.local.json", "settings.json"] {
            let url = cwd.appendingPathComponent(".claude").appendingPathComponent(name)
            guard let cmd = command(at: url) else { continue }
            return cmd.hasSuffix("statusline-pet.py") ? nil : (".claude/" + name, cmd)
        }
        return nil
    }

    /// Modo diagnóstico: `ClaudePet.app/Contents/MacOS/ClaudePet --dump`
    static func dumpAndExit() -> Never {
        print("claude.json  :", LocalUsage.fromClaudeJSON() != nil ? "OK" : "no disponible")
        print("statusLine   :", LocalUsage.fromStatusLine() != nil ? "OK" : "no configurado")
        if let over = statusLineOverride() {
            print("  ⚠️  \(over.layer) de este directorio define su propio statusLine:")
            print("        \(over.command)")
            print("      Las settings del proyecto ganan sobre ~/.claude/settings.json, así que")
            print("      aquí el hook de Claude Pet NO se ejecuta, esté instalado o no.")
            print("      Quítalo de ahí, o haz que ese comando llame también a statusline-pet.py.")
        }
        if let u = LocalUsage.best() {
            print("fuente elegida:", u.source, "|", Fmt.ago(u.fetchedAt))
            for l in u.limits {
                print(String(format: "  %-26@ %3d%%  %-20@ %@",
                             l.label as NSString, l.percent,
                             (l.detail ?? "") as NSString,
                             Fmt.reset(l.resetsAt) as NSString))
            }
            print("peor =", u.worst, "→ humor", Mood.from(u.worst).face)
        } else {
            print("SIN DATOS →", LocalUsage.emptyReason())
        }

        print("")
        print("Permisos que usa esta app:")
        print("  Archivos      : solo ~/.claude.json y ~/.claude/pet-usage.json (el home no")
        print("                  está protegido por TCC, así que no pide nada)")
        print("  Red           : ninguna")
        print("  Automatización: ninguna")
        print("  Accesibilidad : ninguna")
        print("  Notificaciones: se piden la primera vez que hay algo que avisar")
        print("  Inicio sesión : \(loginStatusText())")
        let sem = DispatchSemaphore(value: 0)
        UNUserNotificationCenter.current().getNotificationSettings { st in
            let map: [UNAuthorizationStatus: String] = [
                .notDetermined: "aún no se han pedido",
                .denied: "denegadas",
                .authorized: "concedidas",
                .provisional: "provisionales",
            ]
            print("  → estado actual de notificaciones: \(map[st.authorizationStatus] ?? "?")")
            sem.signal()
        }
        _ = sem.wait(timeout: .now() + 3)
        exit(0)
    }

    @MainActor private func setPet(_ visible: Bool) {
        if visible {
            if panel == nil { panel = PetPanel() }
            panel?.orderFrontRegardless()
        } else {
            panel?.orderOut(nil)
        }
    }
}

@main
struct ClaudePetApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var delegate
    @ObservedObject var store = PetStore.shared

    var body: some Scene {
        MenuBarExtra {
            PanelView()
        } label: {
            let tint = store.tintClawd ? NSColor(store.mood.color) : Clawd.brandNS
            HStack(spacing: 4) {
                Image(nsImage: Clawd.menuBarImage(color: tint, night: store.isNight))
                if let u = store.usage { Text(u.compactText) }
            }
        }
        .menuBarExtraStyle(.window)
    }
}
