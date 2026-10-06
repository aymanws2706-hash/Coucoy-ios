import SwiftUI
import WidgetKit

/// Owns the animated engine and everything the screen can change.
@MainActor
final class MochiModel: ObservableObject {
    let engine = BotEngine()

    @Published private(set) var state: BotState = .idle
    @Published private(set) var outfitSelection: Outfit = Outfit.stored
    @Published var soundOn: Bool = SoundEngine.shared.enabled {
        didSet {
            SoundEngine.shared.enabled = soundOn
            if soundOn { SoundEngine.shared.play("blip") }
        }
    }
    @Published private(set) var islandOn: Bool = UserDefaults.standard.bool(forKey: "islandOn")
    @Published var islandMessage: String?

    /// Where the finger is, -1…1 on each axis (eyes follow it).
    var lookX: CGFloat = 0
    var lookY: CGFloat = 0
    var touching = false

    private var dizzyTask: Task<Void, Never>?

    init() {
        engine.setState(.idle, force: true)
        engine.setOutfit(resolvedOutfit, animated: false)
        NotificationCenter.default.addObserver(forName: .botDizzy, object: nil, queue: .main) { [weak self] _ in
            Task { @MainActor in self?.goDizzy() }
        }
    }

    var resolvedOutfit: Outfit {
        Outfit.resolved(selection: outfitSelection, date: Date(), calendar: .current)
    }

    // MARK: Actions

    func setState(_ s: BotState) {
        dizzyTask?.cancel()
        state = s
        engine.setState(s)
        if let snd = s.sound { SoundEngine.shared.play(snd) }
        if islandOn { LiveIsland.shared.update(state: s, outfit: resolvedOutfit) }
    }

    func emote(_ e: BotEmote) {
        engine.triggerEmote(e)
        let sounds: [BotEmote: String] = [
            .love: "love", .surprised: "pop", .proud: "proud", .wink: "wink", .yawn: "yawn", .happy: "blip",
        ]
        if let snd = sounds[e] { SoundEngine.shared.play(snd) }
    }

    func greet() { engine.greet() }

    func poke() { engine.slap() }

    func setOutfit(_ o: Outfit) {
        outfitSelection = o
        Outfit.stored = o
        engine.setOutfit(resolvedOutfit)
        if islandOn { LiveIsland.shared.update(state: state, outfit: resolvedOutfit) }
        WidgetCenter.shared.reloadAllTimelines()
    }

    func setIsland(_ on: Bool) {
        if on {
            if let err = LiveIsland.shared.start(state: state, outfit: resolvedOutfit) {
                islandMessage = err
                islandOn = false
            } else {
                islandMessage = nil
                islandOn = true
            }
        } else {
            LiveIsland.shared.stop()
            islandOn = false
            islandMessage = nil
        }
        UserDefaults.standard.set(islandOn, forKey: "islandOn")
    }

    /// Called when the app comes to the foreground: iOS ends Live Activities after
    /// a few hours, so put Mochi back if the user wants it there.
    func refreshIsland() {
        guard islandOn else { return }
        if LiveIsland.shared.isRunning {
            LiveIsland.shared.update(state: state, outfit: resolvedOutfit)
        } else if let err = LiveIsland.shared.start(state: state, outfit: resolvedOutfit) {
            islandMessage = err
        }
    }

    /// coucou://state/thinking · coucou://emote/love · coucou://outfit/crown
    /// coucou://island/on · coucou://island/off — usable from the Shortcuts app.
    func handle(url: URL) {
        guard url.scheme == "coucou", let kind = url.host else { return }
        let value = url.pathComponents.dropFirst().first ?? ""
        switch kind {
        case "state": if let s = BotState(rawValue: value) { setState(s) }
        case "emote": if let e = BotEmote(rawValue: value) { emote(e) }
        case "outfit": if let o = Outfit(rawValue: value) { setOutfit(o) }
        case "island": setIsland(value != "off")
        case "greet": greet()
        default: break
        }
    }

    private func goDizzy() {
        state = .dizzy
        engine.setState(.dizzy)
        SoundEngine.shared.play("dizzy")
        dizzyTask?.cancel()
        dizzyTask = Task { @MainActor [weak self] in
            try? await Task.sleep(for: .seconds(3.2))
            guard let self, !Task.isCancelled, self.state == .dizzy else { return }
            self.setState(.idle)
        }
    }
}
