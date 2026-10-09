import SwiftUI

/// Four tabs: talk to Putshi, watch its tasks, play with the character, settings.
struct RootView: View {
    @ObservedObject var model: MochiModel
    @ObservedObject var agent: PutshiAgent
    @State private var tab: Tab = ProcessInfo.processInfo.arguments.contains("-demo") ? .play : .chat

    enum Tab: Hashable { case chat, tasks, play, settings }

    var body: some View {
        TabView(selection: $tab) {
            ChatView(model: model, agent: agent)
                .tabItem { Label("Putshi", systemImage: "bubble.left.and.text.bubble.right.fill") }
                .tag(Tab.chat)
            TasksView(agent: agent)
                .tabItem { Label("Tasks", systemImage: "checklist") }
                .badge(agent.tasks.filter { $0.status == .running }.count)
                .tag(Tab.tasks)
            PlaygroundView(model: model)
                .tabItem { Label("Play", systemImage: "face.smiling") }
                .tag(Tab.play)
            SettingsView(model: model, agent: agent)
                .tabItem { Label("Settings", systemImage: "gearshape.fill") }
                .tag(Tab.settings)
        }
        .tint(Color(hex: "#A78BFA"))
        .preferredColorScheme(.dark)
    }
}

// MARK: - Chat

struct ChatView: View {
    @ObservedObject var model: MochiModel
    @ObservedObject var agent: PutshiAgent
    @State private var draft = ""
    @FocusState private var typing: Bool

    private let suggestions = [
        "Plan my study session for tonight",
        "Explain a stop-loss like I'm new to trading",
        "Open my latest Revit project on the PC",
    ]

    var body: some View {
        VStack(spacing: 0) {
            MochiStage(model: model, headroom: 0.3)
                .frame(height: typing ? 90 : 170)
                .animation(.easeInOut(duration: 0.25), value: typing)
                .padding(.top, 4)

            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 10) {
                        if agent.items.isEmpty { emptyState }
                        ForEach(agent.items) { item in
                            ChatRow(item: item) { allow in agent.answerApproval(itemID: item.id, allow: allow) }
                                .id(item.id)
                        }
                        if agent.busy {
                            Text("Putshi is \(model.state == .working ? "working" : "thinking")…")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                                .id("busy")
                        }
                    }
                    .padding(16)
                }
                .scrollDismissesKeyboard(.interactively)
                .onChange(of: agent.items.count) { _, _ in
                    withAnimation { proxy.scrollTo(agent.items.last?.id, anchor: .bottom) }
                }
            }

            inputBar
        }
        .background(Color(hex: "#0B0D12").ignoresSafeArea())
    }

    private var emptyState: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Ask me anything, or give me a job. I'll plan it, show the steps on your lock screen, and use your PC when I need it.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
            ForEach(suggestions, id: \.self) { s in
                Button { agent.send(s) } label: {
                    Text(s)
                        .font(.subheadline)
                        .padding(.horizontal, 12).padding(.vertical, 8)
                        .background(Color.white.opacity(0.07), in: Capsule())
                }
                .buttonStyle(.plain)
            }
        }
    }

    private var inputBar: some View {
        HStack(spacing: 10) {
            TextField("Message Putshi", text: $draft, axis: .vertical)
                .lineLimit(1...5)
                .focused($typing)
                .padding(.horizontal, 14).padding(.vertical, 10)
                .background(Color.white.opacity(0.08), in: RoundedRectangle(cornerRadius: 20, style: .continuous))
                .submitLabel(.send)
                .onSubmit(send)
            Button(action: send) {
                Image(systemName: "arrow.up")
                    .font(.system(size: 16, weight: .bold))
                    .frame(width: 38, height: 38)
                    .background(canSend ? Color(hex: "#A78BFA") : Color.white.opacity(0.1), in: Circle())
                    .foregroundStyle(canSend ? Color(hex: "#0B0D12") : .secondary)
            }
            .disabled(!canSend)
            .accessibilityLabel("Send")
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(Color(hex: "#0B0D12"))
    }

    private var canSend: Bool { !agent.busy && !draft.trimmingCharacters(in: .whitespaces).isEmpty }

    private func send() {
        guard canSend else { return }
        agent.send(draft)
        draft = ""
    }
}

struct ChatRow: View {
    let item: ChatItem
    let onAnswer: (Bool) -> Void

    var body: some View {
        switch item.kind {
        case .user:
            HStack {
                Spacer(minLength: 40)
                Text(item.text)
                    .padding(.horizontal, 14).padding(.vertical, 10)
                    .background(Color(hex: "#A78BFA").opacity(0.9), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
                    .foregroundStyle(Color(hex: "#0B0D12"))
            }
        case .putshi:
            HStack {
                Text(markdown(item.text))
                    .textSelection(.enabled)
                    .padding(.horizontal, 14).padding(.vertical, 10)
                    .background(Color.white.opacity(0.07), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
                Spacer(minLength: 40)
            }
        case .note:
            Text(item.text)
                .font(.footnote)
                .foregroundStyle(Color(hex: "#FBBF24"))
                .frame(maxWidth: .infinity, alignment: .center)
                .multilineTextAlignment(.center)
        case let .approval(_, question, answered):
            VStack(alignment: .leading, spacing: 10) {
                Label("Your PC is asking", systemImage: "exclamationmark.shield.fill")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(Color(hex: "#F5A524"))
                Text(question).font(.subheadline)
                if let answered {
                    Text(answered ? "Allowed" : "Denied")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(answered ? Color(hex: "#34D399") : Color(hex: "#F4505E"))
                } else {
                    HStack {
                        Button("Deny") { onAnswer(false) }
                            .buttonStyle(.bordered)
                            .tint(Color(hex: "#F4505E"))
                        Button("Allow") { onAnswer(true) }
                            .buttonStyle(.borderedProminent)
                            .tint(Color(hex: "#34D399"))
                    }
                }
            }
            .padding(14)
            .background(Color(hex: "#F5A524").opacity(0.12), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).stroke(Color(hex: "#F5A524").opacity(0.35)))
        }
    }

    private func markdown(_ s: String) -> AttributedString {
        (try? AttributedString(markdown: s, options: .init(interpretedSyntax: .inlineOnlyPreservingWhitespace)))
            ?? AttributedString(s)
    }
}

// MARK: - Tasks

struct TasksView: View {
    @ObservedObject var agent: PutshiAgent

    var body: some View {
        NavigationStack {
            Group {
                if agent.tasks.isEmpty {
                    VStack(spacing: 8) {
                        Image(systemName: "checklist").font(.largeTitle).foregroundStyle(.secondary)
                        Text("No tasks yet").font(.headline)
                        Text("Give Putshi a job in the chat. Its steps show up here and on your lock screen.")
                            .font(.subheadline).foregroundStyle(.secondary)
                            .multilineTextAlignment(.center)
                    }
                    .padding(32)
                } else {
                    List(agent.tasks) { task in
                        TaskCard(task: task)
                            .listRowBackground(Color.white.opacity(0.05))
                    }
                    .scrollContentBackground(.hidden)
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Color(hex: "#0B0D12").ignoresSafeArea())
            .navigationTitle("Tasks")
            .toolbar {
                if agent.tasks.contains(where: { $0.status != .running }) {
                    ToolbarItem(placement: .topBarTrailing) {
                        Button("Clear finished") { agent.clearFinishedTasks() }
                    }
                }
            }
        }
    }
}

struct TaskCard: View {
    let task: PutshiTask

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(task.title).font(.headline)
                Spacer()
                Text(statusLabel)
                    .font(.caption.weight(.semibold))
                    .padding(.horizontal, 8).padding(.vertical, 3)
                    .background(statusColor.opacity(0.2), in: Capsule())
                    .foregroundStyle(statusColor)
            }
            ForEach(task.steps) { step in
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    Image(systemName: icon(step.status))
                        .foregroundStyle(color(step.status))
                        .frame(width: 16)
                    Text(step.text).font(.subheadline)
                    if step.onPC {
                        Text("PC").font(.caption2.weight(.bold)).foregroundStyle(.secondary)
                    }
                }
            }
            if !task.summary.isEmpty {
                Text(task.summary).font(.footnote).foregroundStyle(.secondary)
            }
            Text(task.created, style: .time).font(.caption2).foregroundStyle(.tertiary)
        }
        .padding(.vertical, 6)
    }

    private var statusLabel: String {
        switch task.status {
        case .running: "\(task.doneCount)/\(task.steps.count)"
        case .done: "Done"
        case .failed: "Failed"
        }
    }

    private var statusColor: Color {
        switch task.status {
        case .running: Color(hex: "#3B9EFF")
        case .done: Color(hex: "#34D399")
        case .failed: Color(hex: "#F4505E")
        }
    }

    private func icon(_ s: TaskStep.Status) -> String {
        switch s {
        case .pending: "circle"
        case .running: "circle.dotted.circle"
        case .done: "checkmark.circle.fill"
        case .failed: "xmark.circle.fill"
        }
    }

    private func color(_ s: TaskStep.Status) -> Color {
        switch s {
        case .pending: .secondary
        case .running: Color(hex: "#3B9EFF")
        case .done: Color(hex: "#34D399")
        case .failed: Color(hex: "#F4505E")
        }
    }
}

// MARK: - Settings

struct SettingsView: View {
    @ObservedObject var model: MochiModel
    @ObservedObject var agent: PutshiAgent
    @State private var confirmForget = false
    @ObservedObject private var settings = PutshiSettings.shared
    @State private var pcCheck: String?
    @State private var checking = false

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    SecureField("sk-ant-…", text: $settings.apiKey)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                } header: {
                    Text("Anthropic API key")
                } footer: {
                    Text("The same key JARVIS uses. Stored in the iPhone Keychain, never shared.")
                }

                Section {
                    TextField("https://your-pc.tailnet.ts.net", text: $settings.pcURL)
                        .keyboardType(.URL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    SecureField("Bridge token", text: $settings.pcToken)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    Button(checking ? "Checking…" : "Test connection", action: testPC)
                        .disabled(checking || !settings.hasPC)
                    if let pcCheck {
                        Text(pcCheck).font(.footnote).foregroundStyle(.secondary)
                    }
                } header: {
                    Text("Your PC")
                } footer: {
                    Text("Run the Putshi bridge on your PC, then paste the address and token it prints.")
                }

                Section {
                    if agent.facts.isEmpty {
                        Text("Nothing yet. Tell Putshi things like “remember I use Revit 2025” and they'll show up here.")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    } else {
                        ForEach(agent.facts.reversed()) { fact in
                            VStack(alignment: .leading, spacing: 2) {
                                Text(fact.text)
                                Text(fact.created, style: .date).font(.caption2).foregroundStyle(.tertiary)
                            }
                            .swipeActions {
                                Button("Forget", role: .destructive) { agent.forget(fact) }
                            }
                        }
                        Button("Forget everything", role: .destructive) { confirmForget = true }
                    }
                } header: {
                    Text("Memory")
                } footer: {
                    Text("Putshi reads these in every conversation. Swipe left on one to forget it.")
                }
                .confirmationDialog("Forget everything Putshi remembers?", isPresented: $confirmForget, titleVisibility: .visible) {
                    Button("Forget everything", role: .destructive) { agent.forgetEverything() }
                }

                Section("Character") {
                    Toggle("Putshi in the Dynamic Island", isOn: Binding(get: { model.islandOn }, set: { model.setIsland($0) }))
                    Toggle("Sounds", isOn: $model.soundOn)
                    if let msg = model.islandMessage {
                        Text(msg).font(.footnote).foregroundStyle(Color(hex: "#F4505E"))
                    }
                }

                Section {
                    Text("Putshi is built on Coucou by Louis Raillé (github.com/Louis-CFM/coucou). Engine MIT; character and sounds © Louis Raillé, used here for personal use.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }
            .scrollContentBackground(.hidden)
            .background(Color(hex: "#0B0D12").ignoresSafeArea())
            .navigationTitle("Settings")
        }
    }

    private func testPC() {
        checking = true
        pcCheck = nil
        Task {
            do {
                let name = try await PCBridge.ping()
                pcCheck = "Connected to \(name)."
            }
            catch { pcCheck = error.localizedDescription }
            checking = false
        }
    }
}
