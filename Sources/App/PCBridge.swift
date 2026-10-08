import Foundation

/// Client for the Putshi bridge running on the user's PC (bridge/putshi_bridge.py).
///
/// Protocol (JSON over HTTPS, `Authorization: Bearer <token>`):
///   GET  /putshi/ping                     -> {"ok": true, "name": "..."}
///   POST /putshi/tasks {"instruction"}    -> {"id": "..."}
///   GET  /putshi/tasks/{id}               -> PCTaskStatus
///   POST /putshi/tasks/{id}/approval {"allow": bool}
struct PCTaskStatus: Decodable {
    struct Step: Decodable { let text: String; let status: String }
    struct Approval: Decodable { let question: String }
    let id: String
    let status: String          // queued | running | needs_approval | done | failed
    let steps: [Step]
    let result: String?
    let approval: Approval?
}

@MainActor
enum PCBridge {
    private static func request(_ path: String, method: String = "GET", body: [String: Any]? = nil) async throws -> Data {
        let settings = PutshiSettings.shared
        let base = settings.pcURL.trimmingCharacters(in: CharacterSet(charactersIn: "/ "))
        let token = settings.pcToken
        guard !base.isEmpty, let url = URL(string: base + path) else {
            throw PutshiError(message: "Your PC isn't set up yet. Add its address in Settings.")
        }
        var req = URLRequest(url: url)
        req.httpMethod = method
        req.timeoutInterval = 20
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        if let body {
            req.setValue("application/json", forHTTPHeaderField: "content-type")
            req.httpBody = try JSONSerialization.data(withJSONObject: body)
        }
        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await URLSession.shared.data(for: req)
        } catch {
            throw PutshiError(message: "I can't reach your PC. Is it on, with the Putshi bridge and Tailscale running?")
        }
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        if status == 401 { throw PutshiError(message: "Your PC refused the token. Check the PC token in Settings.") }
        guard (200..<300).contains(status) else { throw PutshiError(message: "Your PC answered with an error (HTTP \(status)).") }
        return data
    }

    static func ping() async throws -> String {
        let data = try await request("/putshi/ping")
        let json = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
        return (json?["name"] as? String) ?? "your PC"
    }

    static func start(_ instruction: String) async throws -> String {
        let data = try await request("/putshi/tasks", method: "POST", body: ["instruction": instruction])
        guard let id = ((try? JSONSerialization.jsonObject(with: data)) as? [String: Any])?["id"] as? String else {
            throw PutshiError(message: "Your PC didn't accept the task.")
        }
        return id
    }

    static func status(_ id: String) async throws -> PCTaskStatus {
        let data = try await request("/putshi/tasks/\(id)")
        do { return try JSONDecoder().decode(PCTaskStatus.self, from: data) }
        catch { throw PutshiError(message: "Your PC sent a task update I couldn't read.") }
    }

    static func answer(_ id: String, allow: Bool) async throws {
        _ = try await request("/putshi/tasks/\(id)/approval", method: "POST", body: ["allow": allow])
    }
}
