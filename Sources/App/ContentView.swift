import SwiftUI

struct ContentView: View {
    @ObservedObject var model: MochiModel

    private let emotes: [(BotEmote?, String)] = [
        (nil, "Greeting"), (.love, "Love"), (.surprised, "Surprised"), (.proud, "Proud"),
        (.wink, "Wink"), (.yawn, "Yawn"), (.happy, "Happy"), (.annoyed, "Annoyed"),
    ]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                header

                ZStack {
                    RadialGradient(colors: [model.state.tint.opacity(model.state == .idle ? 0.08 : 0.25), .clear],
                                   center: .init(x: 0.5, y: 0.65), startRadius: 10, endRadius: 220)
                        .animation(.easeInOut(duration: 0.4), value: model.state)
                    MochiStage(model: model)
                        .padding(.horizontal, 24)
                }
                .padding(.vertical, 8)
                .background(Color.white.opacity(0.04), in: RoundedRectangle(cornerRadius: 28, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 28, style: .continuous).stroke(Color.white.opacity(0.07)))
                .overlay(alignment: .bottom) {
                    Text("Tap to poke · hold for hearts · drag to look around")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .padding(.bottom, 12)
                }

                islandCard

                section("State") {
                    ForEach(BotState.allCases, id: \.self) { s in
                        Chip(title: s.title, selected: model.state == s, tint: s.tint) { model.setState(s) }
                    }
                }

                section("Expressions") {
                    ForEach(emotes, id: \.1) { e in
                        Chip(title: e.1, selected: false, tint: .white) {
                            if let emote = e.0 { model.emote(emote) } else { model.greet() }
                        }
                    }
                }

                section("Outfit") {
                    ForEach(Outfit.allCases, id: \.self) { o in
                        Chip(title: o.displayName, selected: model.outfitSelection == o, tint: .white) {
                            model.setOutfit(o)
                        }
                    }
                }

                Text("Putshi is built on Coucou by Louis Raillé (github.com/Louis-CFM/coucou). Engine MIT; character and sounds © Louis Raillé, used here for personal use.")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .padding(.top, 8)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
        }
        .background(Color(hex: "#0B0D12").ignoresSafeArea())
        .preferredColorScheme(.dark)
    }

    private var header: some View {
        HStack {
            Text("Putshi").font(.system(size: 28, weight: .bold, design: .rounded))
            Spacer()
            Button {
                model.soundOn.toggle()
            } label: {
                Image(systemName: model.soundOn ? "speaker.wave.2.fill" : "speaker.slash.fill")
                    .font(.system(size: 17, weight: .semibold))
                    .frame(width: 40, height: 40)
                    .background(Color.white.opacity(0.08), in: Circle())
            }
            .accessibilityLabel(model.soundOn ? "Sound on" : "Sound off")
        }
    }

    private var islandCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Toggle(isOn: Binding(get: { model.islandOn }, set: { model.setIsland($0) })) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Putshi in the Dynamic Island").font(.body.weight(.semibold))
                    Text("Also shows on the lock screen. iOS removes it after about 8 hours; opening Putshi brings it back.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            .tint(Color(hex: "#34D399"))
            if let msg = model.islandMessage {
                Text(msg).font(.caption).foregroundStyle(Color(hex: "#F4505E"))
            }
        }
        .padding(16)
        .background(Color.white.opacity(0.05), in: RoundedRectangle(cornerRadius: 20, style: .continuous))
    }

    private func section<Content: View>(_ title: String, @ViewBuilder _ content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title.uppercased())
                .font(.caption.weight(.semibold))
                .tracking(1)
                .foregroundStyle(.secondary)
            FlowLayout(spacing: 8) { content() }
        }
    }
}

struct Chip: View {
    let title: String
    let selected: Bool
    let tint: Color
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(title)
                .font(.subheadline.weight(.medium))
                .padding(.horizontal, 14)
                .padding(.vertical, 9)
                .foregroundStyle(selected ? Color(hex: "#0B0D12") : Color.white.opacity(0.85))
                .background(selected ? tint : Color.white.opacity(0.07), in: Capsule())
                .overlay(Capsule().stroke(Color.white.opacity(selected ? 0 : 0.08)))
        }
        .buttonStyle(.plain)
    }
}

/// Wraps chips onto as many rows as needed.
struct FlowLayout: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let maxW = proposal.width ?? .infinity
        var x: CGFloat = 0, y: CGFloat = 0, rowH: CGFloat = 0, widest: CGFloat = 0
        for v in subviews {
            let s = v.sizeThatFits(.unspecified)
            if x > 0 && x + s.width > maxW {
                y += rowH + spacing
                x = 0
                rowH = 0
            }
            x += s.width + spacing
            rowH = max(rowH, s.height)
            widest = max(widest, x - spacing)
        }
        return CGSize(width: proposal.width ?? widest, height: y + rowH)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var x = bounds.minX, y = bounds.minY, rowH: CGFloat = 0
        for v in subviews {
            let s = v.sizeThatFits(.unspecified)
            if x > bounds.minX && x + s.width > bounds.maxX {
                y += rowH + spacing
                x = bounds.minX
                rowH = 0
            }
            v.place(at: CGPoint(x: x, y: y), proposal: ProposedViewSize(s))
            x += s.width + spacing
            rowH = max(rowH, s.height)
        }
    }
}
