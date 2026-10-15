// Personal build: the phone link. Coucou serves a small web app and a JSON API
// on 127.0.0.1:8771 only. Tailscale ("tailscale serve") makes that reachable
// from the user's own devices over HTTPS, nobody else's; every API call also
// needs the private token handed to the phone through the QR code.
//
// The phone page is built with the rest of the front end (phone.html) and read
// from the app's bundled assets, so it always matches this build.

use std::io::Read;
use std::path::PathBuf;
use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use std::time::Duration;

use serde::Serialize;
use serde_json::{json, Value};
use tauri::{AppHandle, Emitter, Manager};
use tiny_http::{Header, Method, Request, Response, Server};

use crate::{agent, claude, day, desk, platform, secrets, sysstats};

pub const PORT: u16 = 8771;
const MAX_BODY: u64 = 64 * 1024;

#[derive(Default)]
pub struct Phone {
    started: AtomicBool,
    /// What the island last published: timer, Claude Code status, alert.
    island: Mutex<Value>,
    /// The phone has its own conversation with Mochi.
    chat: claude::Chat,
    /// https://<pc>.<tailnet>.ts.net/ once Tailscale is serving.
    url: Mutex<Option<String>>,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PhoneInfo {
    pub enabled: bool,
    pub tailscale_found: bool,
    /// The address to open on the phone (without the token).
    pub url: Option<String>,
    /// The same, with the token, as a QR code (SVG markup).
    pub qr_svg: Option<String>,
    /// What Tailscale said, when it needs something from the user.
    pub message: Option<String>,
}

pub fn token() -> Option<String> {
    secrets::get("phone-token").filter(|t| t.len() >= 32)
}

pub fn public_url(app: &AppHandle) -> Option<String> {
    app.state::<Phone>().url.lock().unwrap().clone()
}

/// The island publishes its own state (timer, Claude Code) for the phone.
pub fn publish(app: &AppHandle, snapshot: Value) {
    *app.state::<Phone>().island.lock().unwrap() = snapshot;
}

// ── Setup ────────────────────────────────────────────────────────────────────

fn new_token() -> Result<String, String> {
    let mut bytes = [0u8; 24];
    getrandom::fill(&mut bytes).map_err(|e| e.to_string())?;
    Ok(bytes.iter().map(|b| format!("{b:02x}")).collect())
}

fn tailscale_exe() -> Option<PathBuf> {
    if let Some(p) = platform::find_on_path("tailscale") {
        return Some(p);
    }
    let default = PathBuf::from(r"C:\Program Files\Tailscale\tailscale.exe");
    default.exists().then_some(default)
}

/// Runs a command, giving up after `secs` (Tailscale can sit waiting for the
/// user to enable a feature in their browser). Returns (finished ok, output).
fn run(exe: &PathBuf, args: &[&str], secs: u64) -> (bool, String) {
    let mut cmd = Command::new(exe);
    cmd.args(args).stdout(Stdio::piped()).stderr(Stdio::piped());
    platform::no_console(&mut cmd);
    let Ok(mut child) = cmd.spawn() else { return (false, "Couldn't start Tailscale.".into()) };
    let mut out = child.stdout.take();
    let mut err = child.stderr.take();
    let (tx, rx) = std::sync::mpsc::channel();
    std::thread::spawn(move || {
        let mut text = String::new();
        if let Some(o) = out.as_mut() {
            let _ = o.read_to_string(&mut text);
        }
        if let Some(e) = err.as_mut() {
            let _ = e.read_to_string(&mut text);
        }
        let _ = tx.send(text);
    });
    let deadline = std::time::Instant::now() + Duration::from_secs(secs);
    loop {
        if let Ok(Some(status)) = child.try_wait() {
            let text = rx.recv_timeout(Duration::from_secs(2)).unwrap_or_default();
            return (status.success(), text.trim().to_string());
        }
        if std::time::Instant::now() >= deadline {
            let _ = child.kill();
            let text = rx.recv_timeout(Duration::from_secs(2)).unwrap_or_default();
            return (false, text.trim().to_string());
        }
        std::thread::sleep(Duration::from_millis(200));
    }
}

fn dns_name(exe: &PathBuf) -> Option<String> {
    let (ok, out) = run(exe, &["status", "--json"], 10);
    if !ok {
        return None;
    }
    let v: Value = serde_json::from_str(&out).ok()?;
    let name = v.get("Self")?.get("DNSName")?.as_str()?.trim_end_matches('.').to_string();
    (!name.is_empty()).then_some(name)
}

fn qr(text: &str) -> Option<String> {
    let code = qrcode::QrCode::new(text.as_bytes()).ok()?;
    Some(
        code.render::<qrcode::render::svg::Color>()
            .min_dimensions(200, 200)
            .dark_color(qrcode::render::svg::Color("#000000"))
            .light_color(qrcode::render::svg::Color("#ffffff"))
            .build(),
    )
}

/// Where things stand, for Settings › Phone. Also refreshes the cached URL.
pub fn info(app: &AppHandle) -> PhoneInfo {
    let enabled = token().is_some();
    let exe = tailscale_exe();
    let url = exe.as_ref().and_then(dns_name).map(|d| format!("https://{d}/"));
    *app.state::<Phone>().url.lock().unwrap() = if enabled { url.clone() } else { None };
    let qr_svg = match (&url, token()) {
        (Some(u), Some(t)) => qr(&format!("{u}#t={t}")),
        _ => None,
    };
    PhoneInfo { enabled, tailscale_found: exe.is_some(), url, qr_svg, message: None }
}

/// Turns the phone link on: a token, the local server, and Tailscale serving it.
pub fn enable(app: &AppHandle) -> Result<PhoneInfo, String> {
    if token().is_none() {
        secrets::set("phone-token", &new_token()?)?;
    }
    start(app.clone());
    let Some(exe) = tailscale_exe() else {
        return Ok(PhoneInfo {
            message: Some("Tailscale isn't installed on this PC yet: get it from tailscale.com/download, sign in, then press this button again.".into()),
            ..info(app)
        });
    };
    let port = PORT.to_string();
    let (ok, out) = run(&exe, &["serve", "--bg", &port], 20);
    let mut result = info(app);
    if !ok {
        result.message = Some(if out.is_empty() {
            "Tailscale didn't answer. Make sure it's running and signed in, then try again.".into()
        } else {
            out
        });
    }
    Ok(result)
}

pub fn disable(app: &AppHandle) -> Result<(), String> {
    if let Some(exe) = tailscale_exe() {
        let _ = run(&exe, &["serve", "--https=443", "off"], 10);
    }
    *app.state::<Phone>().url.lock().unwrap() = None;
    secrets::set("phone-token", "")
}

// ── Server ───────────────────────────────────────────────────────────────────

/// Starts the server once; harmless to call again.
pub fn start(app: AppHandle) {
    if app.state::<Phone>().started.swap(true, Ordering::SeqCst) {
        return;
    }
    std::thread::spawn(move || {
        let server = match Server::http(("127.0.0.1", PORT)) {
            Ok(s) => s,
            Err(err) => {
                crate::log::line(format!("phone link: can't listen on {PORT}: {err}"));
                app.state::<Phone>().started.store(false, Ordering::SeqCst);
                return;
            }
        };
        // Fill the URL cache so ntfy alerts can link to the phone page.
        let a = app.clone();
        std::thread::spawn(move || {
            let _ = info(&a);
        });
        for request in server.incoming_requests() {
            let app = app.clone();
            std::thread::spawn(move || handle(&app, request));
        }
    });
}

fn header(name: &str, value: &str) -> Header {
    Header::from_bytes(name.as_bytes(), value.as_bytes()).expect("valid header")
}

fn reply_json(req: Request, status: u16, body: &Value) {
    let resp = Response::from_string(body.to_string())
        .with_status_code(status)
        .with_header(header("Content-Type", "application/json; charset=utf-8"))
        .with_header(header("Cache-Control", "no-store"));
    let _ = req.respond(resp);
}

fn reply_error(req: Request, status: u16, message: &str) {
    reply_json(req, status, &json!({ "error": message }));
}

/// Same length, every byte compared: no early exit to time.
fn same(a: &str, b: &str) -> bool {
    a.len() == b.len() && a.bytes().zip(b.bytes()).fold(0u8, |acc, (x, y)| acc | (x ^ y)) == 0
}

fn authorized(req: &Request) -> bool {
    let Some(token) = token() else { return false };
    req.headers()
        .iter()
        .find(|h| h.field.equiv("Authorization"))
        .map(|h| same(h.value.as_str(), &format!("Bearer {token}")))
        .unwrap_or(false)
}

fn handle(app: &AppHandle, mut req: Request) {
    let path = req.url().split('?').next().unwrap_or("/").to_string();

    if !path.starts_with("/api/") {
        return serve_static(app, req, &path);
    }
    if !authorized(&req) {
        return reply_error(req, 401, "Not paired. Scan the QR code in Coucou › Settings › Phone again.");
    }

    let mut body = String::new();
    if *req.method() == Method::Post {
        let _ = req.as_reader().take(MAX_BODY).read_to_string(&mut body);
    }
    let input: Value = serde_json::from_str(&body).unwrap_or(json!({}));
    let s = |k: &str| input.get(k).and_then(Value::as_str).unwrap_or("").to_string();

    match (req.method().clone(), path.as_str()) {
        (Method::Get, "/api/state") => {
            let state = state(app);
            reply_json(req, 200, &state)
        }
        (Method::Get, "/api/apps") => {
            let apps = app.state::<sysstats::Stats>().top_processes(6);
            reply_json(req, 200, &json!(apps))
        }
        (Method::Post, "/api/chat") => {
            let text = s("text");
            if text.trim().is_empty() {
                return reply_error(req, 400, "Say something first.");
            }
            let model = app.state::<crate::Shared>().settings.lock().unwrap().model.clone();
            let phone = app.state::<Phone>();
            match tauri::async_runtime::block_on(claude::send(app, &phone.chat, &model, text, None)) {
                Ok(reply) => reply_json(req, 200, &json!({ "text": reply.text })),
                Err(err) => reply_error(req, 502, &err),
            }
        }
        (Method::Get, "/api/offline-config") => {
            // What the phone needs to keep going when the PC is off: the key
            // to talk to Claude itself, the model, what Putshi remembers, and
            // where to leave tasks for the PC.
            let model = app.state::<crate::Shared>().settings.lock().unwrap().model.clone();
            let alerts_topic = secrets::get("ntfy-topic").map(|t| t.trim().to_string());
            let jobs_topic = alerts_topic.as_ref().map(|t| format!("{t}-jobs"));
            reply_json(req, 200, &json!({
                "apiKey": secrets::get("anthropic-api-key"),
                "model": model,
                "memory": agent::memory(),
                "jobsTopic": jobs_topic,
                "alertsTopic": alerts_topic,
                "host": sysstats_host(app),
            }))
        }
        (Method::Get, "/api/jobs") => {
            let list = app.state::<crate::jobs::Jobs>().list();
            reply_json(req, 200, &json!(list))
        }
        (Method::Post, "/api/jobs") => {
            let run_at = input.get("runAt").and_then(Value::as_i64);
            let jobs = app.state::<crate::jobs::Jobs>();
            match jobs.add(&s("id"), &s("instruction"), run_at, &s("sig")) {
                Ok(_) => {
                    let _ = app.emit("jobs-changed", ());
                    reply_json(req, 200, &json!({}))
                }
                Err(err) => reply_error(req, 400, &err),
            }
        }
        (Method::Post, "/api/chat/reset") => {
            app.state::<Phone>().chat.reset();
            reply_json(req, 200, &json!({}))
        }
        (Method::Post, "/api/approve") => {
            let id = input.get("id").and_then(Value::as_u64).unwrap_or(0);
            let allow = input.get("allow").and_then(Value::as_bool).unwrap_or(false);
            app.state::<agent::Approvals>().decide(id, allow);
            reply_json(req, 200, &json!({}))
        }
        (Method::Post, "/api/claude") => {
            // A Claude Code permission card: the island owns those, so hand it over.
            let decision = if s("decision") == "allow" { "allow" } else { "deny" };
            let _ = app.emit("phone-claude", decision);
            reply_json(req, 200, &json!({}))
        }
        (Method::Post, "/api/media") => respond_result(req, desk::media(&s("action"))),
        (Method::Post, "/api/volume") => {
            let v = input.get("percent").and_then(Value::as_u64).unwrap_or(50).min(100) as u8;
            respond_result(req, desk::set_volume(v))
        }
        (Method::Post, "/api/mute") => {
            let mic = input.get("mic").and_then(Value::as_bool).unwrap_or(false);
            let muted = input.get("muted").and_then(Value::as_bool).unwrap_or(true);
            respond_result(req, desk::set_mute(mic, muted))
        }
        (Method::Post, "/api/timer") => {
            let minutes = input.get("minutes").and_then(Value::as_f64).unwrap_or(0.0);
            if minutes <= 0.0 {
                let _ = app.emit("timer-stop", ());
            } else {
                let _ = app.emit("timer", json!({ "minutes": minutes, "label": s("label") }));
            }
            reply_json(req, 200, &json!({}))
        }
        (Method::Post, "/api/shortcut") => {
            let which = s("which");
            // From the phone: only the ones that make sense away from the desk.
            if !matches!(which.as_str(), "lock" | "sleep") {
                return reply_error(req, 400, "Not available from the phone.");
            }
            respond_result(req, desk::shortcut(&which))
        }
        _ => reply_error(req, 404, "Unknown request."),
    }
}

fn sysstats_host(app: &AppHandle) -> String {
    app.state::<sysstats::Stats>().sample().host
}

fn respond_result(req: Request, result: Result<(), String>) {
    match result {
        Ok(()) => reply_json(req, 200, &json!({})),
        Err(err) => reply_error(req, 400, &err),
    }
}

fn state(app: &AppHandle) -> Value {
    let stats = app.state::<sysstats::Stats>().sample();
    let dayer = app.state::<day::Day>();
    let weather = tauri::async_runtime::block_on(dayer.weather(false)).ok();
    let events = tauri::async_runtime::block_on(dayer.calendar(false)).unwrap_or_default();
    json!({
        "host": stats.host.clone(),
        "stats": stats,
        "weather": weather,
        "events": events,
        "nowPlaying": desk::now_playing(),
        "controls": desk::controls(false),
        "activity": desk::activity(),
        "approvals": app.state::<agent::Approvals>().pending(),
        "island": app.state::<Phone>().island.lock().unwrap().clone(),
    })
}

fn serve_static(app: &AppHandle, req: Request, path: &str) {
    if path == "/icon.png" {
        let resp = Response::from_data(include_bytes!("../icons/putshi-512.png").to_vec())
            .with_header(header("Content-Type", "image/png"));
        let _ = req.respond(resp);
        return;
    }
    let file = if path == "/" { "phone.html" } else { path.trim_start_matches('/') };
    if file.contains("..") {
        return reply_error(req, 404, "Not found.");
    }
    match app.asset_resolver().get(file.to_string()) {
        Some(asset) => {
            let resp = Response::from_data(asset.bytes().to_vec())
                .with_header(header("Content-Type", asset.mime_type()))
                .with_header(header("Cache-Control", "no-cache"));
            let _ = req.respond(resp);
        }
        None => reply_error(req, 404, "Not found."),
    }
}
