import Foundation

/// Storage shared by the app and the widget through an App Group. When the
/// App Group isn't available (some free-account installs), the app falls back
/// to its own storage and the widget shows a hint instead of the tasks.
enum SharedStore {
    static let groupID = "group.com.aymanws.putshi"
    static let tasksWidgetKind = "PutshiTasks"

    /// The App Group's defaults, or nil when this install has no App Group.
    static let group: UserDefaults? = {
        guard FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: groupID) != nil else { return nil }
        return UserDefaults(suiteName: groupID)
    }()

    /// Where the app keeps its own data: the App Group when present, so the
    /// widget sees the same thing, else the app's standard defaults.
    static var defaults: UserDefaults { group ?? .standard }

    // MARK: Tasks (what the widget shows)

    struct StepSnap: Codable, Hashable {
        var text: String
        var status: String       // pending | running | done | failed
    }

    struct TaskSnap: Codable, Hashable, Identifiable {
        var id: String
        var title: String
        var status: String       // running | done | failed
        var steps: [StepSnap]
        var summary: String
        var created: Date
        var updated: Date

        var doneCount: Int { steps.filter { $0.status == "done" }.count }
        var currentStep: String {
            steps.first(where: { $0.status == "running" })?.text
                ?? steps.first(where: { $0.status == "pending" })?.text
                ?? (status == "done" ? "Done" : summary)
        }
    }

    static func saveTasks(_ tasks: [TaskSnap]) {
        guard let data = try? JSONEncoder().encode(Array(tasks.prefix(30))) else { return }
        defaults.set(data, forKey: "tasks.v1")
    }

    static func loadTasks() -> [TaskSnap] {
        guard let data = defaults.data(forKey: "tasks.v1"),
              let tasks = try? JSONDecoder().decode([TaskSnap].self, from: data) else { return [] }
        return tasks
    }

    // MARK: Memory (facts Putshi keeps about the user)

    struct Fact: Codable, Hashable, Identifiable {
        var id = UUID()
        var text: String
        var created = Date()
    }

    static func saveFacts(_ facts: [Fact]) {
        guard let data = try? JSONEncoder().encode(Array(facts.suffix(100))) else { return }
        defaults.set(data, forKey: "facts.v1")
    }

    static func loadFacts() -> [Fact] {
        guard let data = defaults.data(forKey: "facts.v1"),
              let facts = try? JSONDecoder().decode([Fact].self, from: data) else { return [] }
        return facts
    }
}
