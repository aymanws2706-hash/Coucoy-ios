// Personal build: the tools Mochi's chat can use on this PC, and the approvals
// that guard the ones that change something.
//
// Reading is free: listing folders, finding files, reading text files, the
// PC's stats. Anything that opens, writes or runs waits for Allow / Deny on
// the island, and is denied if nobody answers within two minutes.

use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Mutex;
use std::time::Duration;

use serde_json::{json, Value};
use tauri::{AppHandle, Emitter, Manager};
use tokio::sync::oneshot;

use crate::platform;

const MAX_READ: u64 = 100_000;
const MAX_OUTPUT: usize = 8_000;
const MAX_FOUND: usize = 40;
const MAX_VISITED: usize = 40_000;
const APPROVAL_TIMEOUT: Duration = Duration::from_secs(120);
const COMMAND_TIMEOUT: Duration = Duration::from_secs(60);

// ── Approvals ────────────────────────────────────────────────────────────────

#[derive(Default)]
pub struct Approvals {
    next: AtomicU64,
    waiting: Mutex<HashMap<u64, oneshot::Sender<bool>>>,
}

impl Approvals {
    /// The island answered a card.
    pub fn decide(&self, id: u64, allow: bool) {
        if let Some(tx) = self.waiting.lock().unwrap().remove(&id) {
            let _ = tx.send(allow);
        }
    }
}

async fn ask(app: &AppHandle, what: &str, detail: &str) -> bool {
    let approvals = app.state::<Approvals>();
    let id = approvals.next.fetch_add(1, Ordering::Relaxed) + 1;
    let (tx, rx) = oneshot::channel();
    approvals.waiting.lock().unwrap().insert(id, tx);
    let _ = app.emit("mochi-approval", json!({ "id": id, "what": what, "detail": detail }));
    let allowed = matches!(tokio::time::timeout(APPROVAL_TIMEOUT, rx).await, Ok(Ok(true)));
    approvals.waiting.lock().unwrap().remove(&id);
    let _ = app.emit("mochi-approval-done", id);
    allowed
}

/// A line under the typing dots: what Mochi is doing right now.
pub fn step(app: &AppHandle, text: &str) {
    let _ = app.emit("mochi-step", text);
}

// ── Memory ───────────────────────────────────────────────────────────────────

fn memory_path() -> PathBuf {
    platform::local_dir().join("memory.json")
}

pub fn memory() -> Vec<String> {
    std::fs::read(memory_path())
        .ok()
        .and_then(|b| serde_json::from_slice(&b).ok())
        .unwrap_or_default()
}

fn save_memory(facts: &[String]) -> Result<(), String> {
    let dir = platform::local_dir();
    platform::ensure_private_dir(&dir).map_err(|e| e.to_string())?;
    let json = serde_json::to_vec_pretty(facts).map_err(|e| e.to_string())?;
    std::fs::write(memory_path(), json).map_err(|e| e.to_string())
}

// ── Tool definitions ─────────────────────────────────────────────────────────

pub fn definitions() -> Vec<Value> {
    vec![
        json!({
            "name": "list_folder",
            "description": "List what is in a folder on this PC: names, sizes, dates. Use ~ for the user's home, e.g. ~/Downloads.",
            "input_schema": { "type": "object", "properties": {
                "path": { "type": "string", "description": "Folder path. ~ is the user's home." }
            }, "required": ["path"] }
        }),
        json!({
            "name": "find_files",
            "description": "Search the user's folders (Desktop, Documents, Downloads, Pictures, Videos, Music, OneDrive, or a given folder) for files whose name contains some text. Newest first.",
            "input_schema": { "type": "object", "properties": {
                "name_contains": { "type": "string", "description": "Part of the file name, case-insensitive. Can be an extension like .pdf" },
                "folder": { "type": "string", "description": "Optional folder to search instead of the usual ones." }
            }, "required": ["name_contains"] }
        }),
        json!({
            "name": "read_text_file",
            "description": "Read a text file (txt, md, csv, json, code, logs…). Up to 100 KB.",
            "input_schema": { "type": "object", "properties": {
                "path": { "type": "string" }
            }, "required": ["path"] }
        }),
        json!({
            "name": "pc_status",
            "description": "This PC right now: CPU, memory, disk, network speed, battery, uptime, and the apps using the most CPU and memory.",
            "input_schema": { "type": "object", "properties": {} }
        }),
        json!({
            "name": "open",
            "description": "Open a file, folder, app or web address on this PC, like double-clicking it. The user approves first, except for http(s) links.",
            "input_schema": { "type": "object", "properties": {
                "target": { "type": "string", "description": "A path, an app name like notepad or calc, or a URL." }
            }, "required": ["target"] }
        }),
        json!({
            "name": "write_text_file",
            "description": "Create or overwrite a text file. The user approves first.",
            "input_schema": { "type": "object", "properties": {
                "path": { "type": "string" },
                "content": { "type": "string" }
            }, "required": ["path", "content"] }
        }),
        json!({
            "name": "run_command",
            "description": "Run a PowerShell command on this PC and get its output (60 s limit). The user approves first. Prefer the other tools when they can do the job.",
            "input_schema": { "type": "object", "properties": {
                "command": { "type": "string" },
                "why": { "type": "string", "description": "One short sentence the user sees on the approval card." }
            }, "required": ["command", "why"] }
        }),
        json!({
            "name": "remember",
            "description": "Save a lasting fact about the user or their setup, for every future chat. Only when they share something worth keeping or ask you to remember.",
            "input_schema": { "type": "object", "properties": {
                "fact": { "type": "string" }
            }, "required": ["fact"] }
        }),
        json!({
            "name": "forget",
            "description": "Delete a remembered fact by its number in the memory list.",
            "input_schema": { "type": "object", "properties": {
                "number": { "type": "integer" }
            }, "required": ["number"] }
        }),
    ]
}

// ── Tool execution ───────────────────────────────────────────────────────────

/// Runs one tool. Ok is the text handed back to Claude; Err is reported to it
/// as a failed tool call so it can explain or try something else.
pub async fn run(app: &AppHandle, name: &str, input: &Value) -> Result<String, String> {
    let s = |k: &str| input.get(k).and_then(Value::as_str).unwrap_or("").to_string();
    match name {
        "list_folder" => {
            let path = expand(&s("path"));
            step(app, &format!("Looking in {}", short(&path)));
            list_folder(&path)
        }
        "find_files" => {
            let needle = s("name_contains");
            step(app, &format!("Searching for “{needle}”"));
            let folder = s("folder");
            let roots = if folder.is_empty() { user_folders() } else { vec![expand(&folder)] };
            tokio::task::spawn_blocking(move || find_files(&roots, &needle))
                .await
                .map_err(|e| e.to_string())?
        }
        "read_text_file" => {
            let path = expand(&s("path"));
            step(app, &format!("Reading {}", short(&path)));
            read_text(&path)
        }
        "pc_status" => {
            step(app, "Checking the PC");
            Ok(pc_status(app))
        }
        "open" => {
            let target = s("target");
            let is_web = target.starts_with("http://") || target.starts_with("https://");
            if !is_web && !ask(app, "Open", &target).await {
                return Err("The user said no.".into());
            }
            step(app, &format!("Opening {}", short_str(&target)));
            open(&target)
        }
        "write_text_file" => {
            let path = expand(&s("path"));
            let content = s("content");
            let detail = format!("{}  ({} characters)", path.display(), content.chars().count());
            if !ask(app, "Write a file", &detail).await {
                return Err("The user said no.".into());
            }
            step(app, &format!("Writing {}", short(&path)));
            if let Some(parent) = path.parent() {
                std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
            }
            std::fs::write(&path, content).map_err(|e| e.to_string())?;
            Ok(format!("Wrote {}", path.display()))
        }
        "run_command" => {
            let command = s("command");
            let why = s("why");
            let what = if why.is_empty() { "Run a command".to_string() } else { why };
            if !ask(app, &what, &command).await {
                return Err("The user said no.".into());
            }
            step(app, "Running the command");
            tokio::task::spawn_blocking(move || run_command(&command))
                .await
                .map_err(|e| e.to_string())?
        }
        "remember" => {
            let fact = s("fact");
            if fact.trim().is_empty() {
                return Err("Nothing to remember.".into());
            }
            let mut facts = memory();
            facts.push(fact.trim().to_string());
            save_memory(&facts)?;
            Ok(format!("Remembered. Memory now has {} facts.", facts.len()))
        }
        "forget" => {
            let n = input.get("number").and_then(Value::as_u64).unwrap_or(0) as usize;
            let mut facts = memory();
            if n == 0 || n > facts.len() {
                return Err(format!("No fact number {n}."));
            }
            let gone = facts.remove(n - 1);
            save_memory(&facts)?;
            Ok(format!("Forgot: {gone}"))
        }
        other => Err(format!("Unknown tool {other}")),
    }
}

/// `~` → the home folder; forward slashes are fine on Windows too.
fn expand(path: &str) -> PathBuf {
    let path = path.trim();
    if path == "~" {
        return platform::home_dir();
    }
    if let Some(rest) = path.strip_prefix("~/").or_else(|| path.strip_prefix("~\\")) {
        return platform::home_dir().join(rest);
    }
    PathBuf::from(path)
}

fn short(path: &Path) -> String {
    short_str(&path.display().to_string())
}

fn short_str(s: &str) -> String {
    let home = platform::home_dir().display().to_string();
    let s = s.replacen(&home, "~", 1);
    if s.chars().count() > 48 {
        let tail: String = s.chars().rev().take(45).collect::<Vec<_>>().into_iter().rev().collect();
        format!("…{tail}")
    } else {
        s
    }
}

fn user_folders() -> Vec<PathBuf> {
    let home = platform::home_dir();
    let mut roots: Vec<PathBuf> = ["Desktop", "Documents", "Downloads", "Pictures", "Videos", "Music"]
        .iter()
        .map(|d| home.join(d))
        .collect();
    if let Ok(entries) = std::fs::read_dir(&home) {
        for e in entries.flatten() {
            if e.file_name().to_string_lossy().starts_with("OneDrive") {
                roots.push(e.path());
            }
        }
    }
    roots.into_iter().filter(|p| p.is_dir()).collect()
}

fn list_folder(path: &Path) -> Result<String, String> {
    let entries = std::fs::read_dir(path).map_err(|e| format!("{}: {e}", path.display()))?;
    let mut rows: Vec<(bool, String, u64, i64)> = entries
        .flatten()
        .map(|e| {
            let meta = e.metadata().ok();
            let is_dir = meta.as_ref().map(|m| m.is_dir()).unwrap_or(false);
            let size = meta.as_ref().map(|m| m.len()).unwrap_or(0);
            let modified = meta.as_ref().map(modified_secs).unwrap_or(0);
            (is_dir, e.file_name().to_string_lossy().to_string(), size, modified)
        })
        .collect();
    rows.sort_by(|a, b| b.0.cmp(&a.0).then(a.1.to_lowercase().cmp(&b.1.to_lowercase())));
    let total = rows.len();
    let mut out = format!("{} ({} items)\n", path.display(), total);
    for (is_dir, name, size, modified) in rows.into_iter().take(200) {
        if is_dir {
            out.push_str(&format!("[folder] {name}\n"));
        } else {
            out.push_str(&format!("{name}  {}  modified {}\n", human_size(size), ago(modified)));
        }
    }
    if total > 200 {
        out.push_str(&format!("… and {} more\n", total - 200));
    }
    Ok(out)
}

fn find_files(roots: &[PathBuf], needle: &str) -> Result<String, String> {
    let needle = needle.to_lowercase();
    if needle.trim().is_empty() {
        return Err("Give part of a file name.".into());
    }
    const SKIP: &[&str] = &["node_modules", ".git", "AppData", "$Recycle.Bin", "__pycache__", ".venv", "venv", "target"];
    let mut found: Vec<(i64, PathBuf, u64)> = Vec::new();
    let mut visited = 0usize;
    let mut stack: Vec<(PathBuf, usize)> = roots.iter().map(|r| (r.clone(), 0)).collect();
    while let Some((dir, depth)) = stack.pop() {
        let Ok(entries) = std::fs::read_dir(&dir) else { continue };
        for e in entries.flatten() {
            visited += 1;
            if visited > MAX_VISITED {
                break;
            }
            let name = e.file_name().to_string_lossy().to_string();
            let Ok(meta) = e.metadata() else { continue };
            if meta.is_dir() {
                if depth < 7 && !SKIP.iter().any(|s| name.eq_ignore_ascii_case(s)) {
                    stack.push((e.path(), depth + 1));
                }
            } else if name.to_lowercase().contains(&needle) {
                found.push((modified_secs(&meta), e.path(), meta.len()));
            }
        }
    }
    found.sort_by(|a, b| b.0.cmp(&a.0));
    if found.is_empty() {
        return Ok(format!("Nothing found with “{needle}” in the name."));
    }
    let mut out = format!("{} found, newest first:\n", found.len());
    for (m, p, size) in found.into_iter().take(MAX_FOUND) {
        out.push_str(&format!("{}  {}  modified {}\n", p.display(), human_size(size), ago(m)));
    }
    Ok(out)
}

fn read_text(path: &Path) -> Result<String, String> {
    let meta = std::fs::metadata(path).map_err(|e| format!("{}: {e}", path.display()))?;
    if meta.len() > MAX_READ {
        return Err(format!("{} is {} — too big to read whole.", path.display(), human_size(meta.len())));
    }
    let bytes = std::fs::read(path).map_err(|e| e.to_string())?;
    String::from_utf8(bytes).map_err(|_| "That file isn't plain text.".to_string())
}

fn pc_status(app: &AppHandle) -> String {
    let stats = app.state::<crate::sysstats::Stats>();
    let s = stats.sample();
    let gb = |b: u64| b as f64 / 1024f64.powi(3);
    let mut out = format!(
        "CPU {:.0}%\nMemory {:.1} of {:.1} GB\nDisk C: {:.0} GB free of {:.0} GB\nNetwork down {} up {}\nUp for {} minutes\n",
        s.cpu,
        gb(s.mem_used),
        gb(s.mem_total),
        gb(s.disk_total.saturating_sub(s.disk_used)),
        gb(s.disk_total),
        human_size(s.net_down) + "/s",
        human_size(s.net_up) + "/s",
        s.uptime_secs / 60,
    );
    match s.battery {
        Some(b) => out.push_str(&format!("Battery {b}%{}\n", if s.charging { " (charging)" } else { "" })),
        None => out.push_str("No battery\n"),
    }
    out.push_str("Top apps:\n");
    for p in stats.top_processes(8) {
        out.push_str(&format!("  {}  CPU {:.0}%  memory {}\n", p.name, p.cpu, human_size(p.memory)));
    }
    out
}

fn open(target: &str) -> Result<String, String> {
    #[cfg(windows)]
    {
        let mut cmd = Command::new("cmd");
        cmd.args(["/C", "start", "", target]);
        platform::no_console(&mut cmd);
        cmd.spawn().map_err(|e| e.to_string())?;
    }
    #[cfg(not(windows))]
    {
        Command::new("xdg-open").arg(target).spawn().map_err(|e| e.to_string())?;
    }
    Ok(format!("Opened {target}"))
}

fn run_command(command: &str) -> Result<String, String> {
    #[cfg(windows)]
    let mut cmd = {
        let mut c = Command::new("powershell");
        c.args(["-NoProfile", "-NonInteractive", "-Command", command]);
        platform::no_console(&mut c);
        c
    };
    #[cfg(not(windows))]
    let mut cmd = {
        let mut c = Command::new("sh");
        c.args(["-c", command]);
        c
    };
    cmd.current_dir(platform::home_dir())
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped());
    let child = cmd.spawn().map_err(|e| e.to_string())?;

    // wait_with_output on a thread so a hung command can be given up on.
    let (tx, rx) = std::sync::mpsc::channel();
    std::thread::spawn(move || {
        let _ = tx.send(child.wait_with_output());
    });
    let output = match rx.recv_timeout(COMMAND_TIMEOUT) {
        Ok(result) => result.map_err(|e| e.to_string())?,
        Err(_) => return Err("Still running after 60 s; stopped waiting.".into()),
    };
    let mut text = String::from_utf8_lossy(&output.stdout).to_string();
    let err = String::from_utf8_lossy(&output.stderr);
    if !err.trim().is_empty() {
        text.push_str("\n[stderr]\n");
        text.push_str(&err);
    }
    if text.len() > MAX_OUTPUT {
        let mut cut = MAX_OUTPUT;
        while !text.is_char_boundary(cut) {
            cut -= 1;
        }
        text.truncate(cut);
        text.push_str("\n… (cut)");
    }
    let code = output.status.code().unwrap_or(-1);
    Ok(format!("exit code {code}\n{}", if text.trim().is_empty() { "(no output)" } else { &text }))
}

fn modified_secs(meta: &std::fs::Metadata) -> i64 {
    meta.modified()
        .ok()
        .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

fn ago(secs: i64) -> String {
    if secs == 0 {
        return "?".into();
    }
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);
    let d = (now - secs).max(0);
    match d {
        0..=59 => "just now".into(),
        60..=3599 => format!("{} min ago", d / 60),
        3600..=86399 => format!("{} h ago", d / 3600),
        _ => format!("{} days ago", d / 86400),
    }
}

pub fn human_size(b: u64) -> String {
    let b = b as f64;
    if b >= 1024f64.powi(3) {
        format!("{:.1} GB", b / 1024f64.powi(3))
    } else if b >= 1024f64.powi(2) {
        format!("{:.1} MB", b / 1024f64.powi(2))
    } else if b >= 1024.0 {
        format!("{:.0} KB", b / 1024.0)
    } else {
        format!("{b:.0} B")
    }
}
