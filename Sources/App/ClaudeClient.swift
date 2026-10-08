import Foundation

struct PutshiError: LocalizedError {
    let message: String
    var errorDescription: String? { message }
}

/// Raw HTTP client for the Claude Messages API (Swift has no official SDK).
/// Messages are kept as plain JSON dictionaries so every block the API returns
/// (thinking, tool_use, fallback…) goes back unchanged on the next turn.
enum Claude {
    static let model = "claude-opus-5-5"
    private static let endpoint = URL(string: "https://api.anthropic.com/v1/messages")!

    static func send(
        apiKey: String,
        system: String,
        tools: [[String: Any]],
        messages: [[String: Any]]
    ) async throws -> [String: Any] {
        let body: [String: Any] = [
            "model": model,
            "max_tokens": 16000,
            "system": system,
            "tools": tools,
            "messages": messages,
            "output_config": ["effort": "medium"],
            // On a safety decline, the API retries on Anthropic's recommended model.
            "fallbacks": "default",
            // Cache the system prompt, tools and history between turns.
            "cache_control": ["type": "ephemeral"],
        ]
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.timeoutInterval = 300
        request.setValue("application/json", forHTTPHeaderField: "content-type")
        request.setValue(apiKey, forHTTPHeaderField: "x-api-key")
        request.setValue("2023-06-01", forHTTPHeaderField: "anthropic-version")
        request.setValue("server-side-fallback-2026-07-01", forHTTPHeaderField: "anthropic-beta")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        var attempt = 0
        while true {
            attempt += 1
            let data: Data
            let response: URLResponse
            do {
                (data, response) = try await URLSession.shared.data(for: request)
            } catch {
                if attempt < 3 { try await Task.sleep(for: .seconds(2 * attempt)); continue }
                throw PutshiError(message: "I can't reach Claude right now. Check your internet connection.")
            }
            let status = (response as? HTTPURLResponse)?.statusCode ?? 0
            let json = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] ?? [:]
            if status == 200 { return json }

            let apiMessage = ((json["error"] as? [String: Any])?["message"] as? String) ?? "HTTP \(status)"
            switch status {
            case 401:
                throw PutshiError(message: "Claude rejected the API key. Paste it again in Settings.")
            case 403:
                throw PutshiError(message: "This API key isn't allowed to use \(model). \(apiMessage)")
            case 429, 500...599:
                if attempt < 3 {
                    let wait = Double((response as? HTTPURLResponse)?.value(forHTTPHeaderField: "retry-after") ?? "") ?? Double(3 * attempt)
                    try await Task.sleep(for: .seconds(min(wait, 20)))
                    continue
                }
                throw PutshiError(message: status == 429
                    ? "Claude is busy (rate limit). Try again in a minute."
                    : "Claude had a server problem. Try again shortly.")
            default:
                throw PutshiError(message: "Claude refused the request: \(apiMessage)")
            }
        }
    }
}
