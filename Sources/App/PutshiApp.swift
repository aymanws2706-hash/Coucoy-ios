import SwiftUI

@main
struct PutshiApp: App {
    @StateObject private var model = MochiModel()
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            ContentView(model: model)
                .onOpenURL { model.handle(url: $0) }
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
            (19.5, { model.setState(.thinking) }),
        ]
        var elapsed = 0.5
        for (at, action) in steps {
            try? await Task.sleep(for: .seconds(at - elapsed))
            elapsed = at
            action()
        }
    }
}
