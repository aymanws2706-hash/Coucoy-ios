import SwiftUI

@main
struct PutshiApp: App {
    @StateObject private var model: MochiModel
    @StateObject private var agent: PutshiAgent
    @Environment(\.scenePhase) private var scenePhase

    init() {
        let m = MochiModel()
        _model = StateObject(wrappedValue: m)
        _agent = StateObject(wrappedValue: PutshiAgent(mochi: m))
    }

    var body: some Scene {
        WindowGroup {
            RootView(model: model, agent: agent)
                .onOpenURL(perform: open)
                .task {
                    try? await Task.sleep(for: .milliseconds(500))
                    model.greet()
                    if ProcessInfo.processInfo.arguments.contains("-demo") { await runDemo() }
                }
        }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active { model.refreshIsland() }
        }
    }

    /// putshi://ask?q=… sends a message to Putshi (handy from Shortcuts or Siri);
    /// everything else (state, emote, outfit, island) drives the character.
    private func open(_ url: URL) {
        if url.host == "ask",
           let q = URLComponents(url: url, resolvingAgainstBaseURL: false)?
               .queryItems?.first(where: { $0.name == "q" })?.value {
            agent.send(q)
        } else {
            model.handle(url: url)
        }
    }

    /// Scripted tour used by the CI preview (launched with "-demo"). Times are
    /// seconds after launch; the workflow takes screenshots in between.
    @MainActor
    private func runDemo() async {
        let steps: [(Double, () -> Void)] = [
            (3.0, { model.setState(.working) }),
            (5.5, { model.setState(.thinking) }),
            (8.0, { model.emote(.love) }),
            (9.0, { model.setState(.approval) }),
            (11.0, { model.setOutfit(.crown) }),
            (13.0, { model.setState(.finished) }),
            (14.5, { model.setState(.dizzy) }),
            (16.0, { model.setOutfit(.auto); model.setState(.idle) }),
            (18.0, { model.setIsland(true) }),
            (19.5, { agent.startDemoTask() }),
        ]
        var elapsed = 0.5
        for (at, action) in steps {
            try? await Task.sleep(for: .seconds(at - elapsed))
            elapsed = at
            action()
        }
    }
}
