import Foundation
import Security

/// Secrets (the Anthropic API key, the PC bridge token) live in the iPhone
/// Keychain, never in UserDefaults or in the app bundle.
enum Keychain {
    private static let service = "putshi"

    static func get(_ key: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var out: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &out) == errSecSuccess,
              let data = out as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    static func set(_ key: String, _ value: String?) {
        let base: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
        ]
        SecItemDelete(base as CFDictionary)
        guard let value, !value.isEmpty else { return }
        var add = base
        add[kSecValueData as String] = Data(value.utf8)
        add[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
        SecItemAdd(add as CFDictionary, nil)
    }
}

/// What the user configures in Settings.
@MainActor
final class PutshiSettings: ObservableObject {
    static let shared = PutshiSettings()

    @Published var apiKey: String {
        didSet { Keychain.set("anthropic_api_key", apiKey.trimmingCharacters(in: .whitespacesAndNewlines)) }
    }
    /// HTTPS address of the Putshi bridge on the PC, e.g. https://my-pc.tailnet.ts.net
    @Published var pcURL: String {
        didSet { UserDefaults.standard.set(pcURL.trimmingCharacters(in: .whitespacesAndNewlines), forKey: "pcURL") }
    }
    @Published var pcToken: String {
        didSet { Keychain.set("pc_token", pcToken.trimmingCharacters(in: .whitespacesAndNewlines)) }
    }

    private init() {
        apiKey = Keychain.get("anthropic_api_key") ?? ""
        pcURL = UserDefaults.standard.string(forKey: "pcURL") ?? ""
        pcToken = Keychain.get("pc_token") ?? ""
    }

    var hasKey: Bool { !apiKey.trimmingCharacters(in: .whitespaces).isEmpty }
    var hasPC: Bool { !pcURL.trimmingCharacters(in: .whitespaces).isEmpty }
}
