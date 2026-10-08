import SwiftUI

// MARK: - What the screens show

struct ChatItem: Identifiable {
    enum Kind: Equatable {
        case user
        case putshi
        case note
        case approval(pcTaskID: String, question: String, answered: Bool?)
    }
    let id = UUID()
    var kind: Kind
    var text: String
}

struct TaskStep: Identifiable, Equatable {
    enum Status: String { case pending, running, done, failed }
    let id = UUID()
    var text: String
    var status: Status = .pending
    var onPC = false
}

struct PutshiTask: Identifiable {
    enum Status: String { case running, done, failed }
    let id: String
    var title: String
    var steps: [TaskStep]
    var status: Status = .running
    var summary: String = ""
    let created = Date()

    var doneCount: Int { steps.filter { $0.status == .done }.count }
    var currentStep: String {
        steps.first(where: { $0.status == .running })?.text
            ?? steps.first(where: { $0.status == .pending })?.text
            ?? (status == .done ? "Done" : summary)
    }
}

// MARK: - The agent

/// Putshi's brain on the phone: a Claude tool-use loop. It plans work as tasks
/// (shown in the Tasks tab and the Dynamic Island), answers what it can itself,
/// and hands anything that needs the computer to the Putshi bridge on the PC.
@MainActor
final class PutshiAgent: ObservableObject {
    @Published private(set) var items: [ChatItem] = []
    @Published private(set) var tasks: [PutshiTask] = []
    @Published private(set) var busy = false

    private let mochi: MochiModel
    private let settings = PutshiSettings.shared
    /// Full API history, append-only, exactly as the API returned it.
    private var history: [[String: Any]] = []
    private var approvalWaiters: [String: CheckedContinuation<Bool, Never>] = [:]
    private var idleTask: Task<Void, Never>?

    init(mochi: MochiModel) {
        self.mochi = mochi
    }

    // MARK: Chat

    func send(_ raw: String) {
        let text = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !busy else { return }
        items.append(ChatItem(kind: .user, text: text))
        history.append(["role": "user", "content": text])
        busy = true
        idleTask?.cancel()
        Task {
            await run()
            busy = false
        }
    }

    func clearChat() {
        guard !busy else { return }
        items.removeAll()
        history.removeAll()
    }

    func answerApproval(itemID: UUID, allow: Bool) {
        guard let i = items.firstIndex(where: { $0.id == itemID }),
              case let .approval(pcID, question, nil) = items[i].kind else { return }
        items[i].kind = .approval(pcTaskID: pcID, question: question, answered: allow)
        approvalWaiters.removeValue(forKey: pcID)?.resume(returning: allow)
    }

    // MARK: Loop

    private func run() async {
        guard settings.hasKey else {
            say(note: "Add your Anthropic API key in Settings so I can think.")
            mochi.setState(.question)
            return
        }
        for _ in 0..<30 {
            mochi.setState(.thinking)
            let response: [String: Any]
            do {
                response = try await Claude.send(
                    apiKey: settings.apiKey, system: systemPrompt(), tools: Self.tools, messages: history)
            } catch {
                say(note: error.localizedDescription)
                mochi.setState(.error)
                settle()
                return
            }
            let content = response["content"] as? [[String: Any]] ?? []
            let stop = response["stop_reason"] as? String ?? ""

            if stop == "refusal" {
                // Leave the refused turn out of the history; the next message starts fresh.
                say(note: "I can't help with that one.")
                mochi.setState(.error)
                settle()
                return
            }
            history.append(["role": "assistant", "content": content])

            let text = content
                .filter { $0["type"] as? String == "text" }
                .compactMap { $0["text"] as? String }
                .joined(separator: "\n\n")
                .trimmingCharacters(in: .whitespacesAndNewlines)
            if !text.isEmpty { items.append(ChatItem(kind: .putshi, text: text)) }

            let toolUses = content.filter { $0["type"] as? String == "tool_use" }
            if stop == "tool_use", !toolUses.isEmpty {
                var results: [[String: Any]] = []
                for use in toolUses { results.append(await execute(use)) }
                history.append(["role": "user", "content": results])
                continue
            }
            if stop == "max_tokens" { say(note: "My answer got cut off. Ask me to continue.") }
            mochi.setState(tasks.first?.status == .failed ? .error : .finished)
            settle()
            return
        }
        say(note: "I stopped after many steps so I don't run up your bill. Tell me to keep going if you want.")
        settle()
    }

    /// Back to idle a few seconds after finishing.
    private func settle() {
        idleTask?.cancel()
        idleTask = Task { [weak self] in
            try? await Task.sleep(for: .seconds(4))
            guard let self, !Task.isCancelled, !self.busy else { return }
            self.mochi.setState(.idle)
        }
    }

    private func say(note: String) {
        items.append(ChatItem(kind: .note, text: note))
    }

    // MARK: Tools

    private func execute(_ use: [String: Any]) async -> [String: Any] {
        let id = use["id"] as? String ?? ""
        let name = use["name"] as? String ?? ""
        let input = use["input"] as? [String: Any] ?? [:]
        do {
            let output: String
            switch name {
            case "create_task": output = createTask(input)
            case "update_step": output = try updateStep(input)
            case "finish_task": output = try finishTask(input)
            case "run_on_computer": output = try await runOnComputer(input)
            case "react": output = react(input)
            default: throw PutshiError(message: "Unknown tool \(name).")
            }
            return ["type": "tool_result", "tool_use_id": id, "content": output]
        } catch {
            return ["type": "tool_result", "tool_use_id": id, "content": error.localizedDescription, "is_error": true]
        }
    }

    private func createTask(_ input: [String: Any]) -> String {
        let title = input["title"] as? String ?? "Task"
        let steps = (input["steps"] as? [String] ?? []).map { TaskStep(text: $0) }
        let task = PutshiTask(id: "t\(tasks.count + 1)", title: title, steps: steps)
        tasks.insert(task, at: 0)
        showOnIsland(task)
        return "Created task \(task.id) with \(steps.count) steps."
    }

    private func index(of taskID: String) throws -> Int {
        guard let i = tasks.firstIndex(where: { $0.id == taskID }) else {
            throw PutshiError(message: "No task with id \(taskID).")
        }
        return i
    }

    private func updateStep(_ input: [String: Any]) throws -> String {
        let t = try index(of: input["task_id"] as? String ?? "")
        let n = (input["step"] as? Int ?? 0) - 1
        guard tasks[t].steps.indices.contains(n) else { throw PutshiError(message: "Step \(n + 1) doesn't exist.") }
        let status = TaskStep.Status(rawValue: input["status"] as? String ?? "") ?? .running
        tasks[t].steps[n].status = status
        if status == .running { mochi.setState(.working) }
        showOnIsland(tasks[t])
        return "Step \(n + 1) is now \(status.rawValue)."
    }

    private func finishTask(_ input: [String: Any]) throws -> String {
        let t = try index(of: input["task_id"] as? String ?? "")
        let ok = input["success"] as? Bool ?? true
        tasks[t].status = ok ? .done : .failed
        tasks[t].summary = input["summary"] as? String ?? ""
        if ok {
            for i in tasks[t].steps.indices where tasks[t].steps[i].status != .failed {
                tasks[t].steps[i].status = .done
            }
        }
        mochi.setState(ok ? .finished : .error)
        showOnIsland(tasks[t])
        return "Task \(tasks[t].id) closed."
    }

    private func react(_ input: [String: Any]) -> String {
        if let e = BotEmote(rawValue: input["emote"] as? String ?? "") { mochi.emote(e) }
        return "ok"
    }

    /// Sends an instruction to the PC bridge and follows it until it ends,
    /// mirroring its steps into the task and asking the user for approvals.
    private func runOnComputer(_ input: [String: Any]) async throws -> String {
        let taskID = tasks[try index(of: input["task_id"] as? String ?? "")].id
        let instruction = input["instruction"] as? String ?? ""
        let pcID = try await PCBridge.start(instruction)
        mochi.setState(.working)
        let firstPCStep = tasks[try index(of: taskID)].steps.count
        let deadline = Date().addingTimeInterval(20 * 60)

        while Date() < deadline {
            try await Task.sleep(for: .seconds(2))
            let status = try await PCBridge.status(pcID)

            // Mirror the PC's steps under this task.
            guard let t = tasks.firstIndex(where: { $0.id == taskID }) else { break }
            for (k, step) in status.steps.enumerated() {
                let s = TaskStep.Status(rawValue: step.status) ?? .running
                let idx = firstPCStep + k
                if idx < tasks[t].steps.count {
                    tasks[t].steps[idx].text = step.text
                    tasks[t].steps[idx].status = s
                } else {
                    tasks[t].steps.append(TaskStep(text: step.text, status: s, onPC: true))
                }
            }
            showOnIsland(tasks[t])

            switch status.status {
            case "needs_approval":
                let question = status.approval?.question ?? "Your PC wants to do something. Allow it?"
                mochi.setState(.approval)
                items.append(ChatItem(kind: .approval(pcTaskID: pcID, question: question, answered: nil), text: question))
                let allow = await withCheckedContinuation { approvalWaiters[pcID] = $0 }
                try await PCBridge.answer(pcID, allow: allow)
                mochi.setState(.working)
            case "done":
                return status.result ?? "Done on the PC."
            case "failed":
                throw PutshiError(message: "The PC couldn't finish: \(status.result ?? "unknown error")")
            default:
                continue
            }
        }
        throw PutshiError(message: "The PC task is still running after 20 minutes. I stopped waiting.")
    }

    /// A pretend task for the CI preview only (no API calls): shows how tasks
    /// look in the Tasks tab, the lock screen and the Dynamic Island.
    func startDemoTask() {
        _ = createTask(["title": "Export Revit plans", "steps": ["Open the project on PC", "Export sheets to PDF", "Send the PDFs to phone"]])
        Task {
            for n in 1...3 {
                _ = try? updateStep(["task_id": "t1", "step": n, "status": "running"])
                try? await Task.sleep(for: .seconds(1.2))
                _ = try? updateStep(["task_id": "t1", "step": n, "status": n == 3 ? "running" : "done"])
                if n == 2 { break }
            }
        }
    }

    private func showOnIsland(_ task: PutshiTask) {
        LiveIsland.shared.task = .init(
            title: task.title, step: task.currentStep,
            done: task.doneCount, total: max(task.steps.count, 1))
        if LiveIsland.shared.isRunning {
            LiveIsland.shared.update(state: mochi.state, outfit: mochi.resolvedOutfit)
        } else {
            mochi.setIsland(true)
        }
    }

    // MARK: Prompt and tool definitions

    private func systemPrompt() -> String {
        """
        You are Putshi, a small, warm, sharp assistant living on the user's iPhone as an animated \
        mochi-shaped character. You work alongside JARVIS, the user's AI assistant on their Windows PC.

        Reply in the language the user writes in. Keep replies short and conversational; this is a phone screen. \
        A dry, light joke is welcome when it fits, never at the cost of clarity.

        Think things through before acting. When a request is ambiguous or a plan has a flaw, say so and \
        propose two or three options with their trade-offs instead of guessing.

        For any request that takes more than one step, first call create_task with a short title and the \
        steps you plan, then call update_step as each step starts and ends, and finish with finish_task. \
        The user watches these steps live on their lock screen and Dynamic Island, so keep step names short.

        Anything that needs the computer (files, apps, Revit, running commands, asking JARVIS) goes through \
        run_on_computer with a clear, self-contained instruction. Don't claim you did something on the PC \
        unless run_on_computer returned success. If the PC is unreachable, say so plainly and offer what \
        you can do from the phone instead.

        Use react now and then to show emotion through the character (love, proud, surprised, wink, happy).
        """
    }

    private static let tools: [[String: Any]] = [
        [
            "name": "create_task",
            "description": "Start tracking a multi-step task. The steps appear on the user's lock screen and Dynamic Island. Returns the task id.",
            "strict": true,
            "input_schema": [
                "type": "object",
                "properties": [
                    "title": ["type": "string", "description": "Short title, under 40 characters."],
                    "steps": ["type": "array", "items": ["type": "string"], "description": "Planned steps, each under 40 characters."],
                ],
                "required": ["title", "steps"],
                "additionalProperties": false,
            ],
        ],
        [
            "name": "update_step",
            "description": "Mark a step of a task as running, done or failed. Steps are numbered from 1.",
            "strict": true,
            "input_schema": [
                "type": "object",
                "properties": [
                    "task_id": ["type": "string"],
                    "step": ["type": "integer"],
                    "status": ["type": "string", "enum": ["running", "done", "failed"]],
                ],
                "required": ["task_id", "step", "status"],
                "additionalProperties": false,
            ],
        ],
        [
            "name": "finish_task",
            "description": "Close a task with a one-line summary of the outcome.",
            "strict": true,
            "input_schema": [
                "type": "object",
                "properties": [
                    "task_id": ["type": "string"],
                    "success": ["type": "boolean"],
                    "summary": ["type": "string"],
                ],
                "required": ["task_id", "success", "summary"],
                "additionalProperties": false,
            ],
        ],
        [
            "name": "run_on_computer",
            "description": "Run an instruction on the user's Windows PC through the Putshi bridge (files, apps, commands, JARVIS). Blocks until the PC finishes and returns its result. Risky actions ask the user for approval on the phone.",
            "strict": true,
            "input_schema": [
                "type": "object",
                "properties": [
                    "task_id": ["type": "string", "description": "The task this work belongs to."],
                    "instruction": ["type": "string", "description": "A complete, self-contained instruction for the PC agent."],
                ],
                "required": ["task_id", "instruction"],
                "additionalProperties": false,
            ],
        ],
        [
            "name": "react",
            "description": "Show an emotion through the Putshi character.",
            "strict": true,
            "input_schema": [
                "type": "object",
                "properties": [
                    "emote": ["type": "string", "enum": ["love", "surprised", "proud", "wink", "yawn", "happy", "annoyed"]],
                ],
                "required": ["emote"],
                "additionalProperties": false,
            ],
        ],
    ]
}
