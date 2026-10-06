import Foundation

/// Widgets cannot play sound; BotEngine still calls SoundEngine.shared.play().
@MainActor
final class SoundEngine {
    static let shared = SoundEngine()
    func play(_ name: String) {}
}
