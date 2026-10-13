// Claude API client — the same integration as ClaudeService.swift: multi-turn
// chat with web search, and files sent as document/image/text blocks.
//
// Everything happens here rather than in the island: the API key never leaves
// the Credential Manager, and file bytes never cross the IPC boundary.

use std::sync::Mutex;

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

use tauri::AppHandle;

use crate::{agent, secrets};

const ENDPOINT: &str = "https://api.anthropic.com/v1/messages";
const ANTHROPIC_VERSION: &str = "2023-06-01";
/// Server-side fallback: on a policy decline the API retries the same request on
/// a fallback model inside the same call, so the island never shows a dead end.
const FALLBACK_BETA: &str = "server-side-fallback-2026-07-01";
const MAX_TOKENS: u32 = 4096;
/// Tool rounds per message before Mochi stops and reports back.
const MAX_ROUNDS: usize = 16;
/// Text and code files are inlined; anything larger is skipped, as on macOS.
const MAX_INLINE_TEXT: u64 = 200_000;

pub const DEFAULT_MODEL: &str = "claude-opus-5";

const SYSTEM_PROMPT: &str = "You are Mochi, a personal AI assistant living in a notch at the top of the user's Windows PC screen. \
You have web search, and tools to look at this PC: list folders, find and read files, check the PC's status and top apps. \
You can also open things, write files and run PowerShell commands; those show the user an Allow / Deny card first, so ask for them directly instead of asking permission in chat. \
Think the task through, use the tools as many times as you need, and check your work before you answer. \
If something fails, say what happened and what you tried. Never claim you did something you didn't. \
Respond in the user's language. Keep answers short and useful; the island is small. \
No markdown formatting (no **, no ##, no bullet dashes). Use plain text with line breaks.";

/// The fixed prompt plus what changes: today's date, where things are, and
/// what Mochi has been asked to remember.
fn system_prompt() -> String {
    let t = crate::platform::local_time();
    let home = crate::platform::home_dir();
    let mut prompt = format!(
        "{SYSTEM_PROMPT}\n\nNow: {:04}-{:02}-{:02} {:02}:{:02} (local time). The user's home folder is {}.",
        t.year, t.month, t.day, t.hour, t.minute, home.display()
    );
    let facts = agent::memory();
    if facts.is_empty() {
        prompt.push_str("\n\nMemory: empty. Use the remember tool when the user shares something lasting.");
    } else {
        prompt.push_str("\n\nWhat you remember about the user (numbered, for the forget tool):");
        for (i, f) in facts.iter().enumerate() {
            prompt.push_str(&format!("\n{}. {f}", i + 1));
        }
    }
    prompt
}

#[derive(Default)]
pub struct Chat {
    /// Full multi-turn history, including tool_use / tool_result blocks.
    messages: Mutex<Vec<Value>>,
}

impl Chat {
    pub fn reset(&self) {
        self.messages.lock().unwrap().clear();
    }

    fn is_empty(&self) -> bool {
        self.messages.lock().unwrap().is_empty()
    }

    fn push(&self, message: Value) {
        self.messages.lock().unwrap().push(message);
    }

    fn len(&self) -> usize {
        self.messages.lock().unwrap().len()
    }

    /// Drops everything this turn added, so a failed turn never leaves a
    /// tool call without its result in the history.
    fn truncate(&self, len: usize) {
        self.messages.lock().unwrap().truncate(len);
    }

    fn snapshot(&self) -> Vec<Value> {
        self.messages.lock().unwrap().clone()
    }
}

#[derive(Debug, Clone, Deserialize)]
#[serde(tag = "kind", rename_all = "camelCase")]
pub enum ChatContext {
    File { name: String, path: String },
    Window { app_name: String, title: String, url: Option<String> },
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ChatReply {
    pub text: String,
}

/// One chat turn: Claude may call tools several times before it answers.
/// Returns the assistant's text, or a message the island shows in the note view.
pub async fn send(
    app: &AppHandle,
    chat: &Chat,
    model: &str,
    query: String,
    context: Option<ChatContext>,
) -> Result<ChatReply, String> {
    let key = secrets::get("anthropic-api-key")
        .ok_or_else(|| "API key missing. Open settings.".to_string())?;

    let mut content: Vec<Value> = Vec::new();

    // File / window context rides along with the first message only, exactly
    // like ClaudeService.chat().
    if chat.is_empty() {
        match &context {
            Some(ChatContext::File { name, path }) => {
                if let Some(block) = file_block(path) {
                    content.push(block);
                }
                content.push(json!({ "type": "text", "text": format!("File: {name} (at {path})") }));
            }
            Some(ChatContext::Window { app_name, title, url }) => {
                let mut text = format!("Context — App: {app_name}, Window: {title}");
                if let Some(url) = url {
                    text.push_str(&format!(", URL: {url}"));
                }
                content.push(json!({ "type": "text", "text": text }));
            }
            None => {}
        }
    }
    content.push(json!({ "type": "text", "text": query }));

    let start = chat.len();
    chat.push(json!({ "role": "user", "content": content }));

    let mut tools = agent::definitions();
    tools.push(json!({ "type": "web_search_20260209", "name": "web_search", "max_uses": 5 }));

    let mut last_text = String::new();
    for _ in 0..MAX_ROUNDS {
        let body = json!({
            "model": model,
            "max_tokens": MAX_TOKENS,
            "system": system_prompt(),
            "tools": tools,
            "fallbacks": "default",
            "messages": chat.snapshot(),
        });

        let response = match call(&key, &body).await {
            Ok(v) => v,
            Err(err) => {
                chat.truncate(start);
                return Err(err);
            }
        };

        let stop = response.get("stop_reason").and_then(Value::as_str).unwrap_or("");
        // A policy decline comes back as HTTP 200 with stop_reason "refusal".
        if stop == "refusal" {
            chat.truncate(start);
            let why = response
                .get("stop_details")
                .and_then(|d| d.get("explanation"))
                .and_then(Value::as_str)
                .unwrap_or("Claude declined this one.");
            return Err(why.to_string());
        }

        let Some(blocks) = response.get("content").and_then(Value::as_array).cloned() else {
            chat.truncate(start);
            return Err("Unexpected API response.".into());
        };

        // Store the whole content — tool_use / tool_result blocks included — so the
        // next round and the next turn have the right context.
        chat.push(json!({ "role": "assistant", "content": blocks.clone() }));

        let text = text_of(&blocks);
        if !text.is_empty() {
            last_text = text;
        }

        match stop {
            "tool_use" => {
                let mut results = Vec::new();
                for block in &blocks {
                    if block.get("type").and_then(Value::as_str) != Some("tool_use") {
                        continue;
                    }
                    let id = block.get("id").and_then(Value::as_str).unwrap_or_default();
                    let name = block.get("name").and_then(Value::as_str).unwrap_or_default();
                    let input = block.get("input").cloned().unwrap_or(json!({}));
                    let (out, is_error) = match agent::run(app, name, &input).await {
                        Ok(out) => (out, false),
                        Err(err) => (err, true),
                    };
                    results.push(json!({
                        "type": "tool_result",
                        "tool_use_id": id,
                        "content": out,
                        "is_error": is_error,
                    }));
                }
                chat.push(json!({ "role": "user", "content": results }));
                agent::step(app, "Thinking");
            }
            // A long web search paused the turn; sending it back resumes it.
            "pause_turn" => continue,
            _ => break,
        }
    }

    if last_text.is_empty() {
        return Err("No response text.".into());
    }
    Ok(ChatReply { text: last_text })
}

fn text_of(blocks: &[Value]) -> String {
    blocks
        .iter()
        .filter(|b| b.get("type").and_then(Value::as_str) == Some("text"))
        .filter_map(|b| b.get("text").and_then(Value::as_str))
        .collect::<Vec<_>>()
        .join("\n")
        .trim()
        .to_string()
}

async fn call(key: &str, body: &Value) -> Result<Value, String> {
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(90))
        .build()
        .map_err(|e| e.to_string())?;

    let response = client
        .post(ENDPOINT)
        .header("x-api-key", key)
        .header("anthropic-version", ANTHROPIC_VERSION)
        .header("anthropic-beta", FALLBACK_BETA)
        .header("content-type", "application/json")
        .json(body)
        .send()
        .await
        .map_err(|e| format!("Network error: {e}"))?;

    let status = response.status();
    let text = response.text().await.map_err(|e| e.to_string())?;
    if !status.is_success() {
        // Surface the API's own message, which is what makes a bad key obvious.
        let detail = serde_json::from_str::<Value>(&text)
            .ok()
            .and_then(|v| {
                v.get("error")
                    .and_then(|e| e.get("message"))
                    .and_then(Value::as_str)
                    .map(str::to_string)
            })
            .unwrap_or_else(|| text.chars().take(200).collect());
        return Err(format!("Claude API {status}: {detail}"));
    }
    serde_json::from_str(&text).map_err(|e| format!("Bad API response: {e}"))
}

/// PDF → document block, image → image block, text/code → inline text.
/// Mirrors readFileAsBlock() in ClaudeService.swift.
fn file_block(path: &str) -> Option<Value> {
    let ext = std::path::Path::new(path)
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or("")
        .to_lowercase();

    let media_type = match ext.as_str() {
        "pdf" => Some(("document", "application/pdf")),
        "jpg" | "jpeg" => Some(("image", "image/jpeg")),
        "png" => Some(("image", "image/png")),
        "gif" => Some(("image", "image/gif")),
        "webp" => Some(("image", "image/webp")),
        _ => None,
    };

    if let Some((block_type, media)) = media_type {
        let bytes = std::fs::read(path).ok()?;
        return Some(json!({
            "type": block_type,
            "source": { "type": "base64", "media_type": media, "data": base64(&bytes) },
        }));
    }

    let len = std::fs::metadata(path).ok()?.len();
    if len > MAX_INLINE_TEXT {
        return None;
    }
    let text = std::fs::read_to_string(path).ok()?;
    Some(json!({ "type": "text", "text": format!("File contents:\n{text}") }))
}

/// Small standalone base64 encoder — not worth another dependency.
/// Also used for Stripe's basic auth.
pub(crate) fn base64_for(bytes: &[u8]) -> String {
    base64(bytes)
}

fn base64(bytes: &[u8]) -> String {
    const TABLE: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut out = String::with_capacity(bytes.len().div_ceil(3) * 4);
    for chunk in bytes.chunks(3) {
        let b = [chunk[0], *chunk.get(1).unwrap_or(&0), *chunk.get(2).unwrap_or(&0)];
        let n = ((b[0] as u32) << 16) | ((b[1] as u32) << 8) | b[2] as u32;
        out.push(TABLE[(n >> 18) as usize & 63] as char);
        out.push(TABLE[(n >> 12) as usize & 63] as char);
        out.push(if chunk.len() > 1 { TABLE[(n >> 6) as usize & 63] as char } else { '=' });
        out.push(if chunk.len() > 2 { TABLE[n as usize & 63] as char } else { '=' });
    }
    out
}

#[cfg(test)]
mod tests {
    use super::base64;

    #[test]
    fn base64_matches_rfc4648_vectors() {
        assert_eq!(base64(b""), "");
        assert_eq!(base64(b"f"), "Zg==");
        assert_eq!(base64(b"fo"), "Zm8=");
        assert_eq!(base64(b"foo"), "Zm9v");
        assert_eq!(base64(b"foob"), "Zm9vYg==");
        assert_eq!(base64(b"fooba"), "Zm9vYmE=");
        assert_eq!(base64(b"foobar"), "Zm9vYmFy");
    }
}
