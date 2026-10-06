import SwiftUI
import QuartzCore

/// The animated Mochi: TimelineView drives a Canvas that runs the real
/// BotEngine every frame, exactly like BotCanvasView on the Mac.
struct MochiStage: View {
    @ObservedObject var model: MochiModel
    /// Extra room above the body (fraction of the width) for hats, hearts and sparks.
    var headroom: CGFloat = 0.35

    @State private var pressStart: Date?
    @State private var longPressFired = false

    var body: some View {
        GeometryReader { geo in
            TimelineView(.animation) { timeline in
                Canvas { context, size in
                    _ = timeline.date
                    render(context: context, size: size)
                }
            }
            .contentShape(Rectangle())
            .gesture(touch(in: geo.size))
        }
        .aspectRatio(1 / (1 + headroom), contentMode: .fit)
        .accessibilityLabel("Mochi, \(model.state.title)")
        .accessibilityAddTraits(.isButton)
        .accessibilityAction { model.poke() }
    }

    private func render(context: GraphicsContext, size: CGSize) {
        let e = model.engine
        let now = CACurrentMediaTime()
        let dt = min(0.05, max(0, now - e.lastTime))
        if model.touching {
            e.lookX = model.lookX
            e.lookY = model.lookY
        } else {
            e.lookX *= 0.95
            e.lookY *= 0.95
        }
        e.particleOverhang = size.height - size.width
        e.update(dt: dt)

        var ctx = context
        e.applyDance(&ctx, size: size)
        if e.outfit != .none && e.outfitPresence > 0.05 && abs(e.roll) > 0.001 {
            // Rigid roll: spin body and outfit together, as on the Mac.
            let c = e.bodyCenter(size: size)
            var r = ctx
            r.translateBy(x: c.x, y: c.y)
            r.rotate(by: .radians(e.roll))
            r.translateBy(x: -c.x, y: -c.y)
            e.drawHandsBehind(context: r, size: size)
            e.drawOutfitBehind(context: r, size: size)
            e.draw(context: r, size: size)
            e.drawOutfitFront(context: r, size: size)
        } else {
            e.drawHandsBehind(context: ctx, size: size)
            e.drawOutfitBehind(context: ctx, size: size)
            e.draw(context: ctx, size: size)
            e.drawOutfitFront(context: ctx, size: size)
        }
        e.drawHandsAndExtras(context: ctx, size: size)
    }

    /// Drag: eyes follow the finger. Quick tap: poke. Hold 0.6 s: hearts.
    private func touch(in size: CGSize) -> some Gesture {
        DragGesture(minimumDistance: 0)
            .onChanged { v in
                let cx = size.width / 2
                let cy = size.height - size.width / 2
                model.lookX = CGFloat(tanh(Double(v.location.x - cx) / 140))
                model.lookY = CGFloat(tanh(Double(v.location.y - cy) / 110))
                model.touching = true
                if pressStart == nil {
                    pressStart = Date()
                    longPressFired = false
                    let started = pressStart
                    Task { @MainActor in
                        try? await Task.sleep(for: .milliseconds(600))
                        if pressStart == started, !longPressFired,
                           hypot(v.translation.width, v.translation.height) < 12 {
                            longPressFired = true
                            model.emote(.love)
                        }
                    }
                }
            }
            .onEnded { v in
                model.touching = false
                let moved = hypot(v.translation.width, v.translation.height)
                if !longPressFired, moved < 12 { model.poke() }
                pressStart = nil
            }
    }
}
