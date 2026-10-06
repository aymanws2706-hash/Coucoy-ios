import SwiftUI

@main
struct CoucouApp: App {
    @StateObject private var model = MochiModel()
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            ContentView(model: model)
                .onOpenURL { model.handle(url: $0) }
                .task {
                    try? await Task.sleep(for: .milliseconds(500))
                    model.greet()
                }
        }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active { model.refreshIsland() }
        }
    }
}
