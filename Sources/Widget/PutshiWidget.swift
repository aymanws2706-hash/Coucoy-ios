import WidgetKit
import SwiftUI
import ActivityKit

@main
struct PutshiWidgetBundle: WidgetBundle {
    var body: some Widget {
        MochiHomeWidget()
        TasksWidget()
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
                    Text("Putshi").font(.headline)
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
                .widgetURL(URL(string: "putshi://greet"))
        }
        .configurationDisplayName("Putshi")
        .description("Putshi on your home screen. Sleeps at night, dresses up for the season.")
        .supportedFamilies([.systemSmall, .accessoryCircular, .accessoryRectangular])
    }
}

// MARK: - Home screen tasks widget

struct TasksEntry: TimelineEntry {
    let date: Date
    let tasks: [SharedStore.TaskSnap]
    let shared: Bool        // false: no App Group on this install
}

struct TasksProvider: TimelineProvider {
    func placeholder(in context: Context) -> TasksEntry {
        TasksEntry(date: Date(), tasks: [Self.sample], shared: true)
    }

    func getSnapshot(in context: Context, completion: @escaping (TasksEntry) -> Void) {
        let tasks = SharedStore.loadTasks()
        completion(TasksEntry(date: Date(), tasks: context.isPreview && tasks.isEmpty ? [Self.sample] : tasks,
                              shared: SharedStore.group != nil || context.isPreview))
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<TasksEntry>) -> Void) {
        let entry = TasksEntry(date: Date(), tasks: SharedStore.loadTasks(), shared: SharedStore.group != nil)
        // The app reloads this widget whenever a task changes; this is only a fallback.
        completion(Timeline(entries: [entry], policy: .after(Date().addingTimeInterval(30 * 60))))
    }

    /// Shown in the widget gallery only.
    static let sample = SharedStore.TaskSnap(
        id: "t1", title: "Export Revit plans", status: "running",
        steps: [.init(text: "Open the project on PC", status: "done"),
                .init(text: "Export sheets to PDF", status: "running"),
                .init(text: "Send the PDFs to phone", status: "pending")],
        summary: "", created: Date(), updated: Date())
}

private func stepColor(_ status: String) -> Color {
    switch status {
    case "done": Color(hex: "#34D399")
    case "running": Color(hex: "#3B9EFF")
    case "failed": Color(hex: "#F4505E")
    default: Color.white.opacity(0.35)
    }
}

private func stepIcon(_ status: String) -> String {
    switch status {
    case "done": "checkmark.circle.fill"
    case "running": "circle.dotted.circle"
    case "failed": "xmark.circle.fill"
    default: "circle"
    }
}

struct TaskBlock: View {
    let task: SharedStore.TaskSnap
    let maxSteps: Int

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            HStack(spacing: 6) {
                Text(task.title).font(.subheadline.weight(.semibold)).lineLimit(1)
                Spacer(minLength: 4)
                Text(task.status == "running" ? "\(task.doneCount)/\(task.steps.count)" : (task.status == "done" ? "Done" : "Failed"))
                    .font(.caption2.weight(.bold))
                    .monospacedDigit()
                    .foregroundStyle(stepColor(task.status == "running" ? "running" : task.status))
            }
            ForEach(Array(task.steps.prefix(maxSteps).enumerated()), id: \.offset) { _, step in
                HStack(spacing: 5) {
                    Image(systemName: stepIcon(step.status))
                        .font(.caption2)
                        .foregroundStyle(stepColor(step.status))
                    Text(step.text)
                        .font(.caption)
                        .foregroundStyle(step.status == "pending" ? Color.white.opacity(0.55) : Color.white)
                        .lineLimit(1)
                }
            }
            if task.steps.count > maxSteps {
                Text("+\(task.steps.count - maxSteps) more").font(.caption2).foregroundStyle(.white.opacity(0.5))
            }
        }
    }
}

struct TasksWidgetView: View {
    @Environment(\.widgetFamily) private var family
    let entry: TasksEntry

    private var running: [SharedStore.TaskSnap] { entry.tasks.filter { $0.status == "running" } }
    private var shown: [SharedStore.TaskSnap] {
        let r = running
        return r.isEmpty ? Array(entry.tasks.prefix(1)) : r
    }

    var body: some View {
        if !entry.shared {
            message("Open Putshi to see your tasks here.", sub: "This install can't share tasks with widgets.")
        } else if entry.tasks.isEmpty {
            message("No tasks yet", sub: "Ask Putshi for something with a few steps.")
        } else {
            switch family {
            case .systemSmall: small
            case .systemLarge: large
            default: medium
            }
        }
    }

    private func message(_ title: String, sub: String) -> some View {
        HStack(spacing: 10) {
            MochiPose(state: .idle, outfit: .none, showBadge: false).frame(width: 44, height: 44)
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(.subheadline.weight(.semibold))
                Text(sub).font(.caption).foregroundStyle(.white.opacity(0.6))
            }
            Spacer(minLength: 0)
        }
    }

    private var small: some View {
        let t = shown[0]
        return VStack(alignment: .leading, spacing: 6) {
            HStack {
                MochiPose(state: t.status == "running" ? .working : (t.status == "done" ? .finished : .error),
                          outfit: .none, showBadge: false)
                    .frame(width: 30, height: 30)
                Spacer()
                Text("\(t.doneCount)/\(t.steps.count)").font(.caption.weight(.bold)).monospacedDigit()
            }
            Text(t.title).font(.subheadline.weight(.semibold)).lineLimit(2)
            Text(t.currentStep).font(.caption).foregroundStyle(Color(hex: "#3B9EFF")).lineLimit(2)
            Spacer(minLength: 0)
            ProgressView(value: Double(t.doneCount), total: Double(max(t.steps.count, 1)))
                .tint(Color(hex: "#3B9EFF"))
        }
    }

    private var medium: some View {
        HStack(alignment: .top, spacing: 12) {
            MochiPose(state: running.isEmpty ? .idle : .working, outfit: .none, showBadge: false)
                .frame(width: 46, height: 46)
            TaskBlock(task: shown[0], maxSteps: 4)
            Spacer(minLength: 0)
        }
    }

    private var large: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 8) {
                MochiPose(state: running.isEmpty ? .idle : .working, outfit: .none, showBadge: false)
                    .frame(width: 34, height: 34)
                Text("Putshi tasks").font(.headline)
                Spacer()
                if !running.isEmpty {
                    Text("\(running.count) running").font(.caption.weight(.semibold)).foregroundStyle(Color(hex: "#3B9EFF"))
                }
            }
            ForEach(Array(entry.tasks.sorted { a, b in
                (a.status == "running" ? 0 : 1, b.updated) < (b.status == "running" ? 0 : 1, a.updated)
            }.prefix(3))) { t in
                TaskBlock(task: t, maxSteps: 4)
            }
            Spacer(minLength: 0)
        }
    }
}

struct TasksWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: SharedStore.tasksWidgetKind, provider: TasksProvider()) { entry in
            TasksWidgetView(entry: entry)
                .foregroundStyle(.white)
                .containerBackground(for: .widget) { Color(hex: "#0B0D12") }
                .widgetURL(URL(string: "putshi://open"))
        }
        .configurationDisplayName("Putshi tasks")
        .description("What Putshi is working on, step by step.")
        .supportedFamilies([.systemSmall, .systemMedium, .systemLarge])
    }
}

// MARK: - Dynamic Island + lock screen Live Activity

/// The task line under Putshi: title, current step and a progress bar.
struct TaskLine: View {
    let state: MochiActivityAttributes.ContentState
    let tint: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(state.taskTitle)
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(.white)
                .lineLimit(1)
            Text(state.taskStep)
                .font(.caption)
                .foregroundStyle(tint)
                .lineLimit(1)
            ProgressView(value: Double(state.taskDone), total: Double(max(state.taskTotal, 1)))
                .tint(tint)
            Text("\(state.taskDone) of \(state.taskTotal) steps")
                .font(.caption2)
                .foregroundStyle(.white.opacity(0.6))
                .monospacedDigit()
        }
    }
}

struct MochiLiveActivity: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: MochiActivityAttributes.self) { context in
            let s = BotState(rawValue: context.state.state) ?? .idle
            let o = Outfit(rawValue: context.state.outfit) ?? .none
            let hasTask = !context.state.taskTitle.isEmpty
            // Lock screen banner
            HStack(spacing: 14) {
                MochiPose(state: s, outfit: o, headroom: 0.35)
                    .frame(width: 64, height: 80)
                if hasTask {
                    TaskLine(state: context.state, tint: s.tint)
                } else {
                    VStack(alignment: .leading, spacing: 3) {
                        Text("Putshi · \(s.title)").font(.headline).foregroundStyle(.white)
                        Text(s.caption).font(.subheadline).foregroundStyle(s.tint)
                    }
                }
                Spacer(minLength: 0)
            }
            .padding(14)
            .activityBackgroundTint(Color(hex: "#0B0D12"))
            .activitySystemActionForegroundColor(.white)
            .widgetURL(URL(string: "putshi://open"))
        } dynamicIsland: { context in
            let s = BotState(rawValue: context.state.state) ?? .idle
            let o = Outfit(rawValue: context.state.outfit) ?? .none
            let hasTask = !context.state.taskTitle.isEmpty
            return DynamicIsland {
                DynamicIslandExpandedRegion(.leading) {
                    MochiPose(state: s, outfit: o, headroom: 0.35)
                        .frame(width: 60, height: 76)
                }
                DynamicIslandExpandedRegion(.center) {
                    Group {
                        if hasTask {
                            TaskLine(state: context.state, tint: s.tint)
                        } else {
                            VStack(alignment: .leading, spacing: 2) {
                                Text("Putshi").font(.headline)
                                Text(s.caption).font(.subheadline).foregroundStyle(s.tint)
                            }
                        }
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
                if hasTask {
                    Text("\(context.state.taskDone)/\(context.state.taskTotal)")
                        .font(.caption2.weight(.semibold))
                        .monospacedDigit()
                        .foregroundStyle(s.tint)
                } else {
                    Circle()
                        .fill(s.tint)
                        .frame(width: 10, height: 10)
                }
            } minimal: {
                MochiPose(state: s, outfit: .none, showBadge: false)
                    .frame(width: 22, height: 22)
            }
            .widgetURL(URL(string: "putshi://open"))
            .keylineTint(s.tint)
        }
    }
}
