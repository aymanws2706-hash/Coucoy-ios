import ActivityKit
import Foundation

/// Puts Mochi in the Dynamic Island and on the lock screen with a Live Activity.
/// Free Apple ID: updates happen while the app runs (no push server needed).
/// iOS ends any Live Activity after about 8 hours; reopening the app restarts it.
@MainActor
final class LiveIsland {
    static let shared = LiveIsland()

    var isRunning: Bool { !Activity<MochiActivityAttributes>.activities.isEmpty }

    /// Returns an error message to show, or nil on success.
    @discardableResult
    func start(state: BotState, outfit: Outfit) -> String? {
        guard ActivityAuthorizationInfo().areActivitiesEnabled else {
            return "Live Activities are turned off. Open Settings › Putshi and turn on Live Activities."
        }
        if isRunning {
            update(state: state, outfit: outfit)
            return nil
        }
        let content = ActivityContent(
            state: MochiActivityAttributes.ContentState(state: state.rawValue, outfit: outfit.rawValue),
            staleDate: nil)
        do {
            _ = try Activity.request(
                attributes: MochiActivityAttributes(name: "Putshi"),
                content: content,
                pushType: nil)
            return nil
        } catch {
            return "Could not start: \(error.localizedDescription)"
        }
    }

    func update(state: BotState, outfit: Outfit) {
        let content = ActivityContent(
            state: MochiActivityAttributes.ContentState(state: state.rawValue, outfit: outfit.rawValue),
            staleDate: nil)
        for activity in Activity<MochiActivityAttributes>.activities {
            Task { await activity.update(content) }
        }
    }

    func stop() {
        for activity in Activity<MochiActivityAttributes>.activities {
            Task { await activity.end(nil, dismissalPolicy: .immediate) }
        }
    }
}
