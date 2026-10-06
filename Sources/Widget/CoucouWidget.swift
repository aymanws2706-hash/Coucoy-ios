import WidgetKit
import SwiftUI
import ActivityKit

@main
struct CoucouWidgetBundle: WidgetBundle {
    var body: some Widget {
        MochiHomeWidget()
        MochiLiveActivity()
    }
}

// MARK: - Home screen / lock screen widget

struct MochiEntry: TimelineEntry {
    let date: Date
    let state: BotState
    let outfit: Outfit
}

/// Mochi sleeps at night and hangs out during the day, in the seasonal outfit.
struct MochiProvider: TimelineProvider {
    func placeholder(in context: Context) -> MochiEntry {
        MochiEntry(date: Date(), state: .idle, outfit: .none)
    }

    func getSnapshot(in context: Context, completion: @escaping (MochiEntry) -> Void) {
        completion(entry(at: Date()))
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<MochiEntry>) -> Void) {
        let cal = Calendar.current
        let now = Date()
        let start = cal.dateInterval(of: .hour, for: now)?.start ?? now
        let entries = (0..<24).compactMap { h -> MochiEntry? in
            guard let d = cal.date(byAdding: .hour, value: h, to: start) else { return nil }
            return entry(at: h == 0 ? now : d)
        }
        completion(Timeline(entries: entries, policy: .atEnd))
    }

    private func entry(at date: Date) -> MochiEntry {
        let hour = Calendar.current.component(.hour, from: date)
        let asleep = hour >= 23 || hour < 7
        let outfit = Outfit.seasonal(for: date, calendar: .current)
        return MochiEntry(date: date, state: asleep ? .sleeping : .idle, outfit: outfit)
    }
}

struct MochiWidgetView: View {
    @Environment(\.widgetFamily) private var family
    let entry: MochiEntry

    var body: some View {
        switch family {
        case .accessoryCircular:
            MochiPose(state: entry.state, outfit: .none, showBadge: false)
                .padding(4)
        case .accessoryRectangular:
            HStack(spacing: 6) {
                MochiPose(state: entry.state, outfit: .none, showBadge: false)
                VStack(alignment: .leading) {
                    Text("Mochi").font(.headline)
                    Text(entry.state.caption).font(.caption)
                }
            }
        default:
            VStack(spacing: 4) {
                MochiPose(state: entry.state, outfit: entry.outfit, showBadge: false, headroom: 0.35)
                Text(entry.state == .sleeping ? "Zzz" : "Coucou!")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.white.opacity(0.7))
            }
            .padding(4)
        }
    }
}

struct MochiHomeWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "MochiHome", provider: MochiProvider()) { entry in
            MochiWidgetView(entry: entry)
                .containerBackground(for: .widget) { Color(hex: "#0B0D12") }
                .widgetURL(URL(string: "coucou://greet"))
        }
        .configurationDisplayName("Mochi")
        .description("Mochi on your home screen. Sleeps at night, dresses up for the season.")
        .supportedFamilies([.systemSmall, .accessoryCircular, .accessoryRectangular])
    }
}

// MARK: - Dynamic Island + lock screen Live Activity

struct MochiLiveActivity: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: MochiActivityAttributes.self) { context in
            let s = BotState(rawValue: context.state.state) ?? .idle
            let o = Outfit(rawValue: context.state.outfit) ?? .none
            // Lock screen banner
            HStack(spacing: 14) {
                MochiPose(state: s, outfit: o, headroom: 0.35)
                    .frame(width: 64, height: 80)
                VStack(alignment: .leading, spacing: 3) {
                    Text("Mochi · \(s.title)").font(.headline).foregroundStyle(.white)
                    Text(s.caption).font(.subheadline).foregroundStyle(s.tint)
                }
                Spacer()
            }
            .padding(14)
            .activityBackgroundTint(Color(hex: "#0B0D12"))
            .activitySystemActionForegroundColor(.white)
            .widgetURL(URL(string: "coucou://greet"))
        } dynamicIsland: { context in
            let s = BotState(rawValue: context.state.state) ?? .idle
            let o = Outfit(rawValue: context.state.outfit) ?? .none
            return DynamicIsland {
                DynamicIslandExpandedRegion(.leading) {
                    MochiPose(state: s, outfit: o, headroom: 0.35)
                        .frame(width: 60, height: 76)
                }
                DynamicIslandExpandedRegion(.center) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Mochi").font(.headline)
                        Text(s.caption).font(.subheadline).foregroundStyle(s.tint)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
                DynamicIslandExpandedRegion(.trailing) {
                    Text(s.title)
                        .font(.caption.weight(.semibold))
                        .padding(.horizontal, 8).padding(.vertical, 4)
                        .background(s.tint.opacity(0.25), in: Capsule())
                }
            } compactLeading: {
                MochiPose(state: s, outfit: .none, showBadge: false)
                    .frame(width: 26, height: 26)
            } compactTrailing: {
                Circle()
                    .fill(s.tint)
                    .frame(width: 10, height: 10)
            } minimal: {
                MochiPose(state: s, outfit: .none, showBadge: false)
                    .frame(width: 22, height: 22)
            }
            .widgetURL(URL(string: "coucou://greet"))
            .keylineTint(s.tint)
        }
    }
}
