import AVFoundation

/// Plays Coucou's sounds (bundled in "sounds/" at build time). Mixes with
/// other audio and respects the silent switch, like a game would.
@MainActor
final class SoundEngine {
    static let shared = SoundEngine()

    var enabled: Bool = UserDefaults.standard.object(forKey: "soundOn") as? Bool ?? true {
        didSet { UserDefaults.standard.set(enabled, forKey: "soundOn") }
    }
    var volume: Float = 0.5

    private var players: [String: AVAudioPlayer] = [:]
    private var active: [AVAudioPlayer] = []

    private init() {
        try? AVAudioSession.sharedInstance().setCategory(.ambient, options: [.mixWithOthers])
    }

    func play(_ name: String) {
        guard enabled else { return }
        guard let url = Bundle.main.url(forResource: name, withExtension: "wav", subdirectory: "sounds")
            ?? Bundle.main.url(forResource: name, withExtension: "wav") else { return }
        // A fresh player per play so the same sound can overlap itself.
        guard let p = try? AVAudioPlayer(contentsOf: url) else { return }
        p.volume = volume
        p.play()
        active.append(p)
        active.removeAll { !$0.isPlaying && $0 !== p }
    }
}
