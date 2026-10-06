import SwiftUI
import ActivityKit

// Shared by the app and the widget extension.

extension Notification.Name {
    /// Posted by BotEngine.slap() when Mochi is poked three times in a row.
    static let botDizzy = Notification.Name("notchBuddy.botDizzy")
}

/// What the Dynamic Island / lock screen Live Activity shows.
struct MochiActivityAttributes: ActivityAttributes {
    struct ContentState: Codable, Hashable {
        var state: String      // BotState raw value
        var outfit: String     // Outfit raw value
    }
    var name: String
}

extension BotState {
    var title: String {
        switch self {
        case .idle: "Idle"
        case .working: "Working"
        case .thinking: "Thinking"
        case .searching: "Searching"
        case .approval: "Approval"
        case .question: "Question"
        case .error: "Error"
        case .finished: "Finished"
        case .ratelimit: "Rate limit"
        case .sleeping: "Sleeping"
        case .dizzy: "Dizzy"
        }
    }

    /// Short line for the Dynamic Island and the lock screen.
    var caption: String {
        switch self {
        case .idle: "Just hanging out"
        case .working: "On it…"
        case .thinking: "Thinking…"
        case .searching: "Looking it up…"
        case .approval: "Needs your OK"
        case .question: "Has a question"
        case .error: "Something broke"
        case .finished: "All done!"
        case .ratelimit: "Catching its breath"
        case .sleeping: "Zzz"
        case .dizzy: "Whoa…"
        }
    }

    var tint: Color {
        Color(hex: tintHex)
    }

    var tintHex: String {
        switch self {
        case .idle: "#C9CDD6"
        case .working: "#3B9EFF"
        case .thinking: "#A78BFA"
        case .searching: "#6366F1"
        case .approval: "#F5A524"
        case .question: "#22D3EE"
        case .error: "#F4505E"
        case .finished: "#34D399"
        case .ratelimit: "#FB923C"
        case .sleeping: "#94A2B8"
        case .dizzy: "#F472B6"
        }
    }

    /// Sound played when entering the state (BotStateCfg.sound on the Mac).
    var sound: String? { BotStates[self]?.sound }
}

/// Mochi frozen in one pose, with its outfit — one frame of the real BotEngine.
/// Used where nothing can animate: widgets, the Dynamic Island, the lock screen.
struct MochiPose: View {
    var state: BotState = .idle
    var outfit: Outfit = .none
    var showBadge: Bool = true
    /// Fraction of the height kept free above Mochi so hats are not clipped.
    var headroom: CGFloat = 0

    var body: some View {
        Canvas { context, size in
            let e = BotEngine()
            let cfg = BotStates[state]!
            e.state = state
            e.cfg = cfg
            e.tint = cfg.tint
            e.tilt = cfg.tilt
            if let c = cfg.color.components, c.count >= 3 {
                e.col = (c[0], c[1], c[2])
                e.colT = e.col
            }
            if let look = cfg.look {
                e.yaw = look.x * 0.55
                e.pitch = look.y * 0.5
            }
            e.particleOverhang = size.height - size.width
            e.setOutfit(outfit, animated: false)
            e.drawHandsBehind(context: context, size: size)
            e.drawOutfitBehind(context: context, size: size)
            e.draw(context: context, size: size)
            e.drawOutfitFront(context: context, size: size)
            if showBadge, let badge = cfg.badge {
                e.badge = badge
                e.badgeS = 1
                e.drawHandsAndExtras(context: context, size: size)
            }
        }
        .aspectRatio(1 / (1 + headroom), contentMode: .fit)
    }
}

enum MochiPrefs {
    static var outfit: Outfit { Outfit.stored }
    static var resolvedOutfit: Outfit {
        Outfit.resolved(selection: Outfit.stored, date: Date(), calendar: .current)
    }
}
