// JARVIS — application macOS native (AppKit + WebKit).
//
// Rôle : fenêtre autonome qui affiche l'interface Obsidian Emerald servie par le service local JARVIS
// (127.0.0.1), démarre ce service s'il ne tourne pas, l'arrête proprement en quittant (sauf si le
// démarrage automatique en arrière-plan est activé), fournit la dictée vocale native (Speech, sur
// l'appareil si possible), les téléchargements, les liens externes et les menus standard.
// Aucune page externe n'est chargée dans la fenêtre : seules les adresses 127.0.0.1 sont autorisées.

import AVFoundation
import Cocoa
import Speech
import WebKit

let kPort = ProcessInfo.processInfo.environment["JARVIS_PORT"] ?? "8765"
let kBase = URL(string: "http://127.0.0.1:\(kPort)/")!
let kSupport = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent("JARVIS")
let kDataDir = ProcessInfo.processInfo.environment["JARVIS_DATA_DIR"].map { URL(fileURLWithPath: $0) } ?? kSupport.appendingPathComponent("data")
let kWorkspace = ProcessInfo.processInfo.environment["JARVIS_WORKSPACE"].map { URL(fileURLWithPath: $0) }
    ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("JARVIS")

// MARK: - Service local

final class Service {
    private(set) var process: Process?
    var startedByApp = false

    var resourcesApp: URL { Bundle.main.resourceURL!.appendingPathComponent("app") }

    func healthy(timeout: TimeInterval = 1.5) -> Bool {
        var req = URLRequest(url: kBase.appendingPathComponent("api/health"), timeoutInterval: timeout)
        req.setValue("127.0.0.1:\(kPort)", forHTTPHeaderField: "Host")
        let sem = DispatchSemaphore(value: 0)
        var ok = false
        URLSession.shared.dataTask(with: req) { data, resp, _ in
            if let r = resp as? HTTPURLResponse, r.statusCode == 200, let d = data, String(decoding: d, as: UTF8.self).contains("\"ok\": true") { ok = true }
            sem.signal()
        }.resume()
        _ = sem.wait(timeout: .now() + timeout + 0.5)
        return ok
    }

    func python() -> String {
        for p in ["/usr/bin/python3", "/opt/homebrew/bin/python3", "/usr/local/bin/python3"] where FileManager.default.isExecutableFile(atPath: p) {
            return p
        }
        return "/usr/bin/python3"
    }

    /// Démarre le service s'il ne répond pas. Retourne nil si tout va bien, sinon un message d'erreur lisible.
    func ensureRunning() -> String? {
        if healthy() { return nil }
        try? FileManager.default.createDirectory(at: kDataDir.appendingPathComponent("logs"), withIntermediateDirectories: true)
        let log = kDataDir.appendingPathComponent("logs/jarvis.log")
        if !FileManager.default.fileExists(atPath: log.path) { FileManager.default.createFile(atPath: log.path, contents: nil) }
        let p = Process()
        p.executableURL = URL(fileURLWithPath: python())
        p.arguments = ["-I", resourcesApp.appendingPathComponent("jarvis.py").path, "serve"]
        p.currentDirectoryURL = kDataDir
        // Environnement minimal : l'application ne transmet rien d'autre que l'essentiel au service.
        let inherited = ProcessInfo.processInfo.environment
        var env: [String: String] = [:]
        for k in ["HOME", "USER", "LOGNAME", "TMPDIR", "LANG", "SSH_AUTH_SOCK", "__CF_USER_TEXT_ENCODING"] { env[k] = inherited[k] }
        env["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin"
        env["PWD"] = kDataDir.path
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["JARVIS_DATA_DIR"] = kDataDir.path
        env["JARVIS_WORKSPACE"] = kWorkspace.path
        env["JARVIS_PORT"] = kPort
        env["JARVIS_APP"] = "1"
        p.environment = env
        if let h = try? FileHandle(forWritingTo: log) { h.seekToEndOfFile(); p.standardOutput = h; p.standardError = h }
        do { try p.run() } catch { return "Impossible de lancer le service JARVIS (\(python())) : \(error.localizedDescription)" }
        process = p
        startedByApp = true
        for _ in 0..<80 {
            if healthy(timeout: 0.5) { return nil }
            if !p.isRunning { return "Le service JARVIS s'est arrêté au démarrage. Journal : \(log.path)" }
            Thread.sleep(forTimeInterval: 0.25)
        }
        return "Le service JARVIS ne répond pas. Journal : \(log.path)"
    }

    func token() -> String? {
        try? String(contentsOf: kDataDir.appendingPathComponent("token"), encoding: .utf8).trimmingCharacters(in: .whitespacesAndNewlines)
    }

    /// Arrêt propre via l'API (tâches annulées, voix coupée, aperçus arrêtés).
    func stop() {
        guard let tok = token() else { process?.terminate(); return }
        var req = URLRequest(url: kBase.appendingPathComponent("api/shutdown"), timeoutInterval: 3)
        req.httpMethod = "POST"
        req.setValue(tok, forHTTPHeaderField: "X-Jarvis-Token")
        req.setValue("127.0.0.1:\(kPort)", forHTTPHeaderField: "Host")
        let sem = DispatchSemaphore(value: 0)
        URLSession.shared.dataTask(with: req) { _, _, _ in sem.signal() }.resume()
        _ = sem.wait(timeout: .now() + 3)
        for _ in 0..<20 where healthy(timeout: 0.3) { Thread.sleep(forTimeInterval: 0.2) }
        if let p = process, p.isRunning { p.terminate() }
    }

    /// Le démarrage automatique (LaunchAgent) est géré par le service ; s'il est actif, quitter la fenêtre n'arrête pas le service.
    var autostartEnabled: Bool {
        FileManager.default.fileExists(atPath: FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/LaunchAgents/studio.novalys.jarvis.service.plist").path)
    }
}

// MARK: - Dictée native (Speech) et mot d'activation

/// Deux modes, toujours visibles dans l'interface (bandeau) et désactivables à tout moment :
/// - « commande » : une phrase, déclenchée par le bouton micro (fin après 1,8 s de silence) ;
/// - « mot d'activation » : écoute continue UNIQUEMENT si la reconnaissance se fait sur l'appareil
///   (aucun audio envoyé), détection du mot « Jarvis », puis capture de la demande qui suit.
final class NativeVoice: NSObject {
    weak var web: WKWebView?
    private let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "fr-FR"))
    private let engine = AVAudioEngine()
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var task: SFSpeechRecognitionTask?
    private var silence: DispatchWorkItem?
    private var restart: DispatchWorkItem?
    private var wakeEnabled = false
    private var wakePaused = false
    private var wakePhrase = "jarvis"
    private var awake = false          // mot détecté : on capture la demande
    private var generation = 0         // invalide les rappels d'une session précédente

    func send(_ event: [String: Any]) {
        guard let data = try? JSONSerialization.data(withJSONObject: event), let json = String(data: data, encoding: .utf8) else { return }
        DispatchQueue.main.async { self.web?.evaluateJavaScript("window.jarvisNativeVoice && window.jarvisNativeVoice.emit(\(json))") }
    }

    private func authorize(_ then: @escaping () -> Void) {
        SFSpeechRecognizer.requestAuthorization { status in
            guard status == .authorized else {
                self.send(["type": "error", "error": "not-allowed", "message": "Reconnaissance vocale non autorisée : Réglages Système > Confidentialité et sécurité > Reconnaissance vocale > JARVIS."])
                return
            }
            AVCaptureDevice.requestAccess(for: .audio) { granted in
                guard granted else {
                    self.send(["type": "error", "error": "not-allowed", "message": "Micro non autorisé : Réglages Système > Confidentialité et sécurité > Microphone > JARVIS."])
                    return
                }
                DispatchQueue.main.async { then() }
            }
        }
    }

    private static func fold(_ s: String) -> String {
        s.folding(options: [.diacriticInsensitive, .caseInsensitive], locale: Locale(identifier: "fr_FR"))
    }

    // MARK: commande unique (bouton micro)
    func start() {
        wakePaused = true
        authorize { self.begin(wake: false) }
    }

    func finish() { request?.endAudio() }

    // MARK: mot d'activation
    func startWake(phrase: String) {
        wakePhrase = NativeVoice.fold(phrase.isEmpty ? "jarvis" : phrase)
        authorize {
            guard let rec = self.recognizer, rec.supportsOnDeviceRecognition else {
                self.send(["type": "error", "error": "wake-unavailable",
                           "message": "Mot d'activation indisponible : ce Mac ne peut pas reconnaître le français sur l'appareil, et JARVIS n'envoie pas d'écoute continue sur Internet. Utilisez le bouton micro ou le raccourci Alt+Espace."])
                return
            }
            self.wakeEnabled = true
            self.wakePaused = false
            self.begin(wake: true)
        }
    }

    func stopWake() {
        wakeEnabled = false
        awake = false
        stopEngine()
        send(["type": "wake_stopped"])
    }

    func pauseWake(_ paused: Bool) {
        wakePaused = paused
        guard wakeEnabled else { return }
        if paused { if !awake && task != nil { stopEngine() } } else if task == nil { begin(wake: true) }
    }

    private func armSilence(_ seconds: Double, _ block: @escaping () -> Void) {
        silence?.cancel()
        let w = DispatchWorkItem(block: block)
        silence = w
        DispatchQueue.main.asyncAfter(deadline: .now() + seconds, execute: w)
    }

    private func stopEngine() {
        generation += 1
        silence?.cancel()
        restart?.cancel()
        if engine.isRunning { engine.stop() }
        engine.inputNode.removeTap(onBus: 0)
        request?.endAudio()
        task?.cancel()
        task = nil
        request = nil
    }

    private func begin(wake: Bool) {
        stopEngine()
        let gen = generation
        guard let rec = recognizer, rec.isAvailable else {
            send(["type": "error", "error": "network", "message": "Reconnaissance vocale indisponible pour le français sur ce Mac."]); return
        }
        let req = SFSpeechAudioBufferRecognitionRequest()
        req.shouldReportPartialResults = true
        if rec.supportsOnDeviceRecognition { req.requiresOnDeviceRecognition = true }
        request = req
        let input = engine.inputNode
        input.installTap(onBus: 0, bufferSize: 1024, format: input.outputFormat(forBus: 0)) { buf, _ in req.append(buf) }
        engine.prepare()
        do { try engine.start() } catch {
            send(["type": "error", "error": "audio-capture", "message": "Micro indisponible : \(error.localizedDescription)"]); return
        }
        awake = false
        send(["type": wake ? "wake_listening" : "start", "onDevice": req.requiresOnDeviceRecognition])
        var commandStart: String.Index? = nil
        task = rec.recognitionTask(with: req) { [weak self] result, error in
            guard let self = self, gen == self.generation else { return }
            if let r = result {
                let text = r.bestTranscription.formattedString
                if wake && !self.awake {
                    let folded = NativeVoice.fold(text)
                    if let range = folded.range(of: self.wakePhrase, options: .backwards) {
                        self.awake = true
                        let offset = folded.distance(from: folded.startIndex, to: range.upperBound)
                        commandStart = text.index(text.startIndex, offsetBy: min(offset, text.count))
                        NSSound(named: "Tink")?.play()
                        self.send(["type": "wake_detected"])
                        self.armSilence(6) { self.endCommand(text: "", wake: true) }
                    }
                    return
                }
                let command = wake ? String(text[(commandStart ?? text.startIndex)...]).trimmingCharacters(in: .whitespacesAndNewlines.union(.punctuationCharacters))
                                   : text
                self.send(["type": "result", "text": command, "final": false])
                self.armSilence(1.8) { self.endCommand(text: command, wake: wake) }
                if r.isFinal && !wake { self.endCommand(text: command, wake: false) }
            }
            if let e = error as NSError?, result == nil {
                if wake {
                    // fin de session de reconnaissance (limite de durée) : on relance l'écoute du mot d'activation
                    DispatchQueue.main.async { if self.wakeEnabled && !self.wakePaused { self.begin(wake: true) } }
                } else {
                    if e.code != 216 && e.code != 1110 { self.send(["type": "error", "error": "no-speech", "message": e.localizedDescription]) }
                    self.endCommand(text: "", wake: false)
                }
            }
        }
        if wake {
            // les sessions de reconnaissance sont limitées dans le temps : relance périodique tant qu'aucun mot n'est détecté
            let w = DispatchWorkItem { [weak self] in
                guard let self = self, gen == self.generation, !self.awake, self.wakeEnabled, !self.wakePaused else { return }
                self.begin(wake: true)
            }
            restart = w
            DispatchQueue.main.asyncAfter(deadline: .now() + 50, execute: w)
        } else {
            armSilence(8) { self.endCommand(text: "", wake: false) }
            DispatchQueue.main.asyncAfter(deadline: .now() + 30) { [weak self] in if gen == self?.generation { self?.finish() } }
        }
    }

    private func endCommand(text: String, wake: Bool) {
        stopEngine()
        let t = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if !t.isEmpty { send(["type": "result", "text": t, "final": true, "confidence": 0]) }
        send(["type": "end", "wake": wake])
        awake = false
        // après une demande, l'écoute du mot d'activation reprend quand l'interface la relance (fin de réponse vocale)
        if wake && wakeEnabled && t.isEmpty && !wakePaused { begin(wake: true) }
        if !wake && wakeEnabled { wakePaused = true }
    }

    func stop(silent: Bool) {
        stopEngine()
        awake = false
        if !silent { send(["type": "end"]) }
    }
}

// MARK: - Fenêtre et navigation

final class WebController: NSObject, WKNavigationDelegate, WKUIDelegate, WKScriptMessageHandler, WKDownloadDelegate {
    let web: WKWebView
    let voice = NativeVoice()

    override init() {
        let cfg = WKWebViewConfiguration()
        cfg.websiteDataStore = .default()
        let ucc = WKUserContentController()
        cfg.userContentController = ucc
        cfg.preferences.setValue(true, forKey: "developerExtrasEnabled")
        web = WKWebView(frame: .zero, configuration: cfg)
        super.init()
        ucc.add(self, name: "jarvisVoice")
        ucc.add(self, name: "jarvisApp")
        web.navigationDelegate = self
        web.uiDelegate = self
        web.setValue(false, forKey: "drawsBackground")
        voice.web = web
    }

    func userContentController(_ ucc: WKUserContentController, didReceive message: WKScriptMessage) {
        guard let body = message.body as? [String: Any], let cmd = body["cmd"] as? String else { return }
        if message.name == "jarvisVoice" {
            switch cmd {
            case "start": voice.start()
            case "finish": voice.finish()
            case "wake_start": voice.startWake(phrase: body["phrase"] as? String ?? "jarvis")
            case "wake_stop": voice.stopWake()
            case "wake_pause": voice.pauseWake(true)
            case "wake_resume": voice.pauseWake(false)
            default: voice.stop(silent: false)
            }
        } else if message.name == "jarvisApp", cmd == "open", let s = body["url"] as? String, let u = URL(string: s),
                  ["http", "https"].contains(u.scheme ?? "") {
            NSWorkspace.shared.open(u)
        }
    }

    // Seules les pages locales de JARVIS s'affichent dans la fenêtre ; tout autre lien s'ouvre dans le navigateur par défaut.
    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        if action.shouldPerformDownload { decisionHandler(.download); return }
        guard let url = action.request.url else { decisionHandler(.cancel); return }
        if url.scheme == "blob" || url.scheme == "data" || url.scheme == "about" { decisionHandler(.allow); return }
        if url.host == "127.0.0.1" && url.port.map(String.init) == kPort { decisionHandler(.allow); return }
        if ["http", "https", "mailto"].contains(url.scheme ?? "") { NSWorkspace.shared.open(url) }
        decisionHandler(.cancel)
    }

    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for action: WKNavigationAction,
                 windowFeatures: WKWindowFeatures) -> WKWebView? {
        // Même liste blanche que la navigation : aucun schéma file:, personnalisé ou d'application n'est transmis au système.
        if let url = action.request.url, ["http", "https", "mailto"].contains(url.scheme?.lowercased() ?? "") { NSWorkspace.shared.open(url) }
        return nil
    }

    func webView(_ webView: WKWebView, navigationAction: WKNavigationAction, didBecome download: WKDownload) { download.delegate = self }

    func download(_ download: WKDownload, decideDestinationUsing response: URLResponse, suggestedFilename: String,
                  completionHandler: @escaping (URL?) -> Void) {
        let dir = FileManager.default.urls(for: .downloadsDirectory, in: .userDomainMask)[0]
        var dest = dir.appendingPathComponent(suggestedFilename)
        var n = 1
        while FileManager.default.fileExists(atPath: dest.path) {
            n += 1
            dest = dir.appendingPathComponent("\((suggestedFilename as NSString).deletingPathExtension)-\(n).\((suggestedFilename as NSString).pathExtension)")
        }
        completionHandler(dest)
    }

    func downloadDidFinish(_ download: WKDownload) {
        web.evaluateJavaScript("window.jarvisNativeToast && window.jarvisNativeToast('Fichier enregistré dans Téléchargements.')")
    }

    func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo,
                 completionHandler: @escaping () -> Void) {
        let a = NSAlert(); a.messageText = message; a.runModal(); completionHandler()
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) { showOffline(error.localizedDescription) }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) { showOffline(error.localizedDescription) }

    func showOffline(_ why: String) {
        let html = """
        <html><body style="background:#080A0B;color:#E9F0EE;font:15px -apple-system;display:grid;place-items:center;height:100vh;margin:0">
        <div style="text-align:center;max-width:460px"><div style="width:64px;height:64px;margin:0 auto 18px;border-radius:50%;
        background:radial-gradient(circle,#38F5B3 0 20%,#00D6A0 35%,#075B48 65%,transparent 67%)"></div>
        <h2 style="font-weight:500">Le service JARVIS ne répond pas</h2><p style="color:#929D99">\(why)</p>
        <p style="color:#929D99">Menu JARVIS &gt; Redémarrer le service, ou consultez le journal (Aide &gt; Ouvrir le journal).</p></div></body></html>
        """
        web.loadHTMLString(html, baseURL: nil)
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate {
    var window: NSWindow!
    let service = Service()
    let controller = WebController()

    func applicationDidFinishLaunching(_ n: Notification) {
        buildMenu()
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1440, height: 900),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView], backing: .buffered, defer: false)
        window.title = "JARVIS"
        window.titlebarAppearsTransparent = true
        window.appearance = NSAppearance(named: .darkAqua)
        window.backgroundColor = NSColor(red: 8 / 255, green: 10 / 255, blue: 11 / 255, alpha: 1)
        window.minSize = NSSize(width: 760, height: 560)
        window.contentView = controller.web
        window.delegate = self
        window.setFrameAutosaveName("JARVISFenetrePrincipale")
        if !window.setFrameUsingName("JARVISFenetrePrincipale") { window.center() }
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        startService()
    }

    func startService() {
        controller.showOffline("Démarrage du service local…")
        DispatchQueue.global().async {
            let err = self.service.ensureRunning()
            DispatchQueue.main.async {
                if let e = err { self.controller.showOffline(e) } else { self.controller.web.load(URLRequest(url: kBase)) }
            }
        }
    }

    // Fermer la fenêtre ne quitte pas l'application (comportement macOS) ; un clic sur l'icône la rouvre.
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if !flag { window.makeKeyAndOrderFront(nil) }
        return true
    }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        controller.voice.stop(silent: true)
        // Quitter l'application arrête le service, sauf si l'utilisateur a choisi le service en arrière-plan (démarrage automatique).
        if !service.autostartEnabled { service.stop() }
        return .terminateNow
    }

    @objc func reload() { controller.web.reload() }
    @objc func restartService() {
        DispatchQueue.global().async {
            self.service.stop()
            DispatchQueue.main.async { self.startService() }
        }
    }
    @objc func openLog() { NSWorkspace.shared.open(kDataDir.appendingPathComponent("logs/jarvis.log")) }
    @objc func openData() { NSWorkspace.shared.open(kDataDir) }
    @objc func openWorkspace() {
        try? FileManager.default.createDirectory(at: kWorkspace, withIntermediateDirectories: true)
        NSWorkspace.shared.open(kWorkspace)
    }
    @objc func goSettings() { controller.web.evaluateJavaScript("location.hash = '#/parametres'") }
    @objc func goDiagnostic() { controller.web.evaluateJavaScript("location.hash = '#/diagnostic'") }

    func buildMenu() {
        let main = NSMenu()
        func item(_ title: String, _ action: Selector?, _ key: String = "", _ mods: NSEvent.ModifierFlags = .command) -> NSMenuItem {
            let i = NSMenuItem(title: title, action: action, keyEquivalent: key); i.keyEquivalentModifierMask = mods; return i
        }
        let app = NSMenu(title: "JARVIS")
        app.addItem(item("À propos de JARVIS", #selector(NSApplication.orderFrontStandardAboutPanel(_:))))
        app.addItem(.separator())
        app.addItem(item("Paramètres…", #selector(goSettings), ","))
        app.addItem(item("Diagnostic", #selector(goDiagnostic), "d", [.command, .shift]))
        app.addItem(item("Redémarrer le service", #selector(restartService)))
        app.addItem(.separator())
        app.addItem(item("Masquer JARVIS", #selector(NSApplication.hide(_:)), "h"))
        app.addItem(item("Quitter JARVIS", #selector(NSApplication.terminate(_:)), "q"))
        let edit = NSMenu(title: "Édition")
        edit.addItem(item("Annuler", Selector(("undo:")), "z"))
        edit.addItem(item("Rétablir", Selector(("redo:")), "z", [.command, .shift]))
        edit.addItem(.separator())
        edit.addItem(item("Couper", #selector(NSText.cut(_:)), "x"))
        edit.addItem(item("Copier", #selector(NSText.copy(_:)), "c"))
        edit.addItem(item("Coller", #selector(NSText.paste(_:)), "v"))
        edit.addItem(item("Tout sélectionner", #selector(NSText.selectAll(_:)), "a"))
        let view = NSMenu(title: "Présentation")
        view.addItem(item("Recharger", #selector(reload), "r"))
        view.addItem(item("Plein écran", #selector(NSWindow.toggleFullScreen(_:)), "f", [.command, .control]))
        let win = NSMenu(title: "Fenêtre")
        win.addItem(item("Réduire", #selector(NSWindow.performMiniaturize(_:)), "m"))
        win.addItem(item("Fermer la fenêtre", #selector(NSWindow.performClose(_:)), "w"))
        let help = NSMenu(title: "Aide")
        help.addItem(item("Ouvrir le journal", #selector(openLog)))
        help.addItem(item("Ouvrir le dossier des données", #selector(openData)))
        help.addItem(item("Ouvrir l'espace de travail", #selector(openWorkspace)))
        for m in [app, edit, view, win, help] {
            let top = NSMenuItem(); top.submenu = m; main.addItem(top)
        }
        NSApp.mainMenu = main
        NSApp.windowsMenu = win
        NSApp.helpMenu = help
    }
}

// SIGTERM (déconnexion, `kill`) : même chemin qu'un « Quitter » normal, donc arrêt propre du service.
signal(SIGTERM, SIG_IGN)
let sigterm = DispatchSource.makeSignalSource(signal: SIGTERM, queue: .main)
sigterm.setEventHandler { NSApp.terminate(nil) }
sigterm.resume()

let application = NSApplication.shared
let delegate = AppDelegate()
application.delegate = delegate
application.setActivationPolicy(.regular)
application.run()
