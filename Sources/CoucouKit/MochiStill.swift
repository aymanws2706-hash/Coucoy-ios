import SwiftUI

/// Mochi in a fixed pose: one frame of BotEngine, no animation, no timer.
/// For surfaces that can't animate (widgets, lists on the iPhone). The Mac
/// island keeps its animated BotCanvasView / MiniBotCanvasView.
struct MochiStill: View {
    var state: BotState = .idle
    /// Overrides the state's eyes (e.g. .closed for a sleeping agent).
    var eye: EyeShape? = nil
    /// Body color; white by default, like the mockups.
    var bodyHex: String = "#FFFFFF"
    var showBadge: Bool = true

    var body: some View {
        Canvas { context, size in
            let engine = BotEngine()
            engine.isMini = true
            engine.bodyColor = cgColorFromHex(bodyHex)
            engine.state = state
            engine.cfg = BotStates[state]!
            if let eye {
                engine.permanentEye = eye
                engine.eyeOverride = eye
                engine.eyeOverrideUntil = .greatestFiniteMagnitude
            }
            engine.draw(context: context, size: size)
            if showBadge, let badge = engine.cfg.badge {
                engine.badge = badge
                engine.badgeS = 1
                engine.drawHandsAndExtras(context: context, size: size)
            }
        }
        .aspectRatio(1, contentMode: .fit)
    }
}
