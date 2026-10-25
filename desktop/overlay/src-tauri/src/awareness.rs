// Personal build: Awareness — Putshi notices commitments ("I'll call you
// back", "send me the plans tomorrow") and offers a reminder.
//
// Three levels, each off until the user turns it on in Settings › Awareness:
//   titles  — which app and window title is in front (kept in memory only);
//   apps    — when a chosen messaging app is in front, a picture of that window;
//   screen  — a picture of the whole screen every 15 minutes while in use.
// Pictures go to Claude for reading and are never written to disk. Anything on
// the ignore list (and private browsing windows) is never captured or noted.
// Tray › Pause stops everything.

use std::collections::VecDeque;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use tauri::{AppHandle, Emitter, Manager};

use crate::{platform, push, secrets};

const ANALYSIS_MODEL: &str = "claude-haiku-4-5";
const APP_EVERY: Duration = Duration::from_secs(3 * 60);
const SCREEN_EVERY: Duration = Duration::from_secs(15 * 60);
const TITLES_EVERY: Duration = Duration::from_secs(30 * 60);

#[derive(Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase", default)]
pub struct Config {
    pub titles: bool,
    pub apps: bool,
    pub screen: bool,
    /// New WhatsApp messages, read from Windows' notifications.
    pub whatsapp: bool,
    /// Process names (without .exe) or words in a window title.
    pub watch: Vec<String>,
    pub ignore: Vec<String>,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            titles: false,
            apps: false,
            screen: false,
            whatsapp: false,
            watch: ["WhatsApp", "ms-teams", "Teams", "OUTLOOK", "Telegram", "Discord", "Messenger", "Signal"]
                .map(String::from)
                .to_vec(),
            ignore: ["1Password", "Bitwarden", "KeePass", "LastPass", "Dashlane", "bank", "banque", "Banking", "PayPal"]
                .map(String::from)
                .to_vec(),
        }
    }
}

#[derive(Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct Suggestion {
    pub id: String,
    pub text: String,
    /// Local time as "2026-10-16T18:30", when the source says when.
    pub when: Option<String>,
    pub why: String,
}

#[derive(Default)]
pub struct Awareness {
    config: Mutex<Option<Config>>,
    titles: Mutex<VecDeque<(String, String, String)>>, // (time, app, title)
    suggested: Mutex<VecDeque<String>>,
    started: AtomicBool,
}

fn config_path() -> std::path::PathBuf {
    platform::local_dir().join("awareness.json")
}

impl Awareness {
    pub fn config(&self) -> Config {
        let mut c = self.config.lock().unwrap();
        if c.is_none() {
            *c = Some(
                std::fs::read(config_path())
                    .ok()
                    .and_then(|b| serde_json::from_slice(&b).ok())
                    .unwrap_or_default(),
            );
        }
        c.clone().unwrap()
    }

    pub fn set_config(&self, cfg: Config) -> Result<(), String> {
        let _ = platform::ensure_private_dir(&platform::local_dir());
        let json = serde_json::to_vec_pretty(&cfg).map_err(|e| e.to_string())?;
        std::fs::write(config_path(), json).map_err(|e| e.to_string())?;
        if !cfg.titles {
            self.titles.lock().unwrap().clear();
        }
        *self.config.lock().unwrap() = Some(cfg);
        Ok(())
    }
}

fn matches_any(list: &[String], app: &str, title: &str) -> bool {
    let app = app.to_lowercase();
    let title = title.to_lowercase();
    list.iter()
        .map(|w| w.trim().to_lowercase())
        .filter(|w| !w.is_empty())
        .any(|w| app.contains(&w) || title.contains(&w))
}

fn is_private(title: &str) -> bool {
    let t = title.to_lowercase();
    ["inprivate", "incognito", "private browsing", "navigation privée", "navigation inprivate"]
        .iter()
        .any(|k| t.contains(k))
}

fn now_label() -> String {
    let t = platform::local_time();
    format!("{:04}-{:02}-{:02} {:02}:{:02}", t.year, t.month, t.day, t.hour, t.minute)
}

// ── The watcher ──────────────────────────────────────────────────────────────

pub fn start(app: AppHandle) {
    if app.state::<Awareness>().started.swap(true, Ordering::SeqCst) {
        return;
    }
    std::thread::spawn(move || {
        let mut last_key = String::new();
        let mut since = Instant::now();
        let mut last_app_shot: std::collections::HashMap<String, Instant> = Default::default();
        let mut last_screen = Instant::now();
        let mut last_titles = Instant::now();
        let mut watching_was = false;
        let mut last_whatsapp = Instant::now();
        loop {
            std::thread::sleep(Duration::from_secs(5));
            let aw = app.state::<Awareness>();
            let cfg = aw.config();
            let paused = crate::integrations::PAUSED.load(Ordering::Relaxed);
            let watching = !paused && (cfg.titles || cfg.apps || cfg.screen || cfg.whatsapp);
            if watching != watching_was {
                watching_was = watching;
                let _ = app.emit("awareness", json!({ "watching": watching }));
            }
            if !watching || secrets::get("anthropic-api-key").is_none() {
                continue;
            }

            // New WhatsApp messages, every 30 s.
            if cfg.whatsapp && last_whatsapp.elapsed() >= Duration::from_secs(30) {
                last_whatsapp = Instant::now();
                let fresh: Vec<_> = app
                    .state::<crate::whatsapp::WhatsApp>()
                    .fresh()
                    .into_iter()
                    .filter(|m| !matches_any(&cfg.ignore, "WhatsApp", &m.chat))
                    .collect();
                if !fresh.is_empty() {
                    let _ = app.emit("awareness", json!({ "watching": true, "looking": true }));
                    analyze(&app, None, &format!("New WhatsApp messages:\n{}", crate::whatsapp::describe(&fresh)));
                    continue;
                }
            }
            if !(cfg.titles || cfg.apps || cfg.screen) {
                continue;
            }
            let Some((exe, title)) = imp::foreground() else { continue };
            if title.is_empty() || matches_any(&cfg.ignore, &exe, &title) || is_private(&title) {
                continue;
            }
            // Putshi's own windows aren't interesting.
            if exe.eq_ignore_ascii_case("Putshi") || exe.eq_ignore_ascii_case("coucou") {
                continue;
            }

            let key = format!("{exe}|{title}");
            if key != last_key {
                last_key = key;
                since = Instant::now();
                if cfg.titles {
                    let mut t = aw.titles.lock().unwrap();
                    t.push_back((now_label(), exe.clone(), title.clone()));
                    while t.len() > 300 {
                        t.pop_front();
                    }
                }
            }

            // A watched app that has been in front for 15 s: read it.
            if cfg.apps && matches_any(&cfg.watch, &exe, &title) && since.elapsed() >= Duration::from_secs(15) {
                let due = last_app_shot.get(&exe).map(|t| t.elapsed() >= APP_EVERY).unwrap_or(true);
                if due {
                    last_app_shot.insert(exe.clone(), Instant::now());
                    if let Some(jpeg) = imp::capture(true) {
                        let _ = app.emit("awareness", json!({ "watching": true, "looking": true }));
                        analyze(&app, Some(jpeg), &format!("The user is in {exe}: \"{title}\"."));
                        continue;
                    }
                }
            }

            // The whole screen, every 15 minutes while the PC is in use.
            if cfg.screen && last_screen.elapsed() >= SCREEN_EVERY && imp::idle_secs() < 60 {
                last_screen = Instant::now();
                if let Some(jpeg) = imp::capture(false) {
                    let _ = app.emit("awareness", json!({ "watching": true, "looking": true }));
                    analyze(&app, Some(jpeg), &format!("A look at the whole screen. In front: {exe}: \"{title}\"."));
                    continue;
                }
            }

            // Titles alone, every half hour.
            if cfg.titles && !cfg.screen && last_titles.elapsed() >= TITLES_EVERY {
                last_titles = Instant::now();
                analyze(&app, None, "Only window titles this time.");
            }
        }
    });
}

/// Asks Claude whether anything in what's in front deserves a reminder.
fn analyze(app: &AppHandle, jpeg: Option<Vec<u8>>, context: &str) {
    let Some(key) = secrets::get("anthropic-api-key") else { return };
    let aw = app.state::<Awareness>();
    let titles: Vec<String> = aw
        .titles
        .lock()
        .unwrap()
        .iter()
        .rev()
        .take(40)
        .map(|(t, a, w)| format!("{t}  {a}: {w}"))
        .collect();
    let already: Vec<String> = aw.suggested.lock().unwrap().iter().cloned().collect();

    let mut content = Vec::new();
    if let Some(bytes) = jpeg {
        content.push(json!({
            "type": "image",
            "source": { "type": "base64", "media_type": "image/jpeg", "data": crate::claude::base64_for(&bytes) }
        }));
    }
    content.push(json!({ "type": "text", "text": format!(
        "Now: {}. {}\n\nRecent windows (newest first):\n{}\n\nAlready suggested (don't repeat):\n{}",
        now_label(),
        context,
        if titles.is_empty() { "(not tracked)".to_string() } else { titles.join("\n") },
        if already.is_empty() { "(none)".to_string() } else { already.join("\n") },
    )}));

    let system = "You help the user not forget things. Look at what's on their screen and find clear, specific \
commitments or requests that need a follow-up from THEM: they promised to call, reply, send, pay or do something, \
someone asked them for something, or a meeting or deadline was set. Ignore ads, news, code, and anything vague. \
Most of the time there is nothing: answer []. Answer ONLY with a JSON array of at most 2 items: \
{\"text\": \"Call Karim back about the villa plans\", \"when\": \"2026-10-16T18:30\" or null, \"why\": \"Karim on WhatsApp: 'call me tonight'\"}. \
Write text and why in the same language as the conversation. Pick a sensible time when one is implied ('tonight' = 19:00).";

    let body = json!({
        "model": ANALYSIS_MODEL,
        "max_tokens": 400,
        "system": system,
        "messages": [{ "role": "user", "content": content }],
    });
    let app = app.clone();
    tauri::async_runtime::spawn(async move {
        let Ok(client) = reqwest::Client::builder().timeout(Duration::from_secs(60)).build() else { return };
        let resp = client
            .post("https://api.anthropic.com/v1/messages")
            .header("x-api-key", key)
            .header("anthropic-version", "2023-06-01")
            .json(&body)
            .send()
            .await;
        let Ok(resp) = resp else { return };
        if !resp.status().is_success() {
            crate::log::line(format!("awareness: Claude answered {}", resp.status()));
            return;
        }
        let Ok(v) = resp.json::<Value>().await else { return };
        let text: String = v
            .get("content")
            .and_then(Value::as_array)
            .map(|blocks| {
                blocks
                    .iter()
                    .filter_map(|b| b.get("text").and_then(Value::as_str))
                    .collect::<Vec<_>>()
                    .join("")
            })
            .unwrap_or_default();
        let (Some(a), Some(b)) = (text.find('['), text.rfind(']')) else { return };
        let Ok(items) = serde_json::from_str::<Vec<Value>>(&text[a..=b]) else { return };
        let aw = app.state::<Awareness>();
        for item in items.into_iter().take(2) {
            let s = |k: &str| item.get(k).and_then(Value::as_str).unwrap_or("").trim().to_string();
            let text = s("text");
            if text.is_empty() {
                continue;
            }
            {
                let mut seen = aw.suggested.lock().unwrap();
                if seen.iter().any(|t| t.eq_ignore_ascii_case(&text)) {
                    continue;
                }
                seen.push_back(text.clone());
                while seen.len() > 50 {
                    seen.pop_front();
                }
            }
            let when = Some(s("when")).filter(|w| w.len() >= 16);
            let suggestion = Suggestion {
                id: format!("s{}", std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map(|d| d.as_millis()).unwrap_or(0)),
                text: text.clone(),
                when,
                why: s("why"),
            };
            let _ = app.emit("suggestion", &suggestion);
            push::send(&app, "💡 Putshi noticed", &format!("{text}\nOpen Putshi to set the reminder."));
        }
    });
}

// ── Windows: what's in front, idle time, screen capture ──────────────────────

#[cfg(windows)]
mod imp {
    use windows::core::PWSTR;
    use windows::Win32::Foundation::{CloseHandle, HWND, RECT};
    use windows::Win32::Graphics::Gdi::{
        BitBlt, CreateCompatibleBitmap, CreateCompatibleDC, DeleteDC, DeleteObject, GetDC, GetDIBits, ReleaseDC,
        SelectObject, BITMAPINFO, BITMAPINFOHEADER, BI_RGB, DIB_RGB_COLORS, SRCCOPY,
    };
    use windows::Win32::System::SystemInformation::GetTickCount;
    use windows::Win32::System::Threading::{
        OpenProcess, QueryFullProcessImageNameW, PROCESS_NAME_WIN32, PROCESS_QUERY_LIMITED_INFORMATION,
    };
    use windows::Win32::UI::Input::KeyboardAndMouse::{GetLastInputInfo, LASTINPUTINFO};
    use windows::Win32::UI::WindowsAndMessaging::{
        GetForegroundWindow, GetSystemMetrics, GetWindowRect, GetWindowTextW, GetWindowThreadProcessId, SM_CXSCREEN,
        SM_CYSCREEN,
    };

    pub fn foreground() -> Option<(String, String)> {
        unsafe {
            let hwnd = GetForegroundWindow();
            if hwnd.0.is_null() {
                return None;
            }
            let mut buf = [0u16; 512];
            let n = GetWindowTextW(hwnd, &mut buf);
            let title = String::from_utf16_lossy(&buf[..n.max(0) as usize]);
            Some((process_name(hwnd).unwrap_or_default(), title))
        }
    }

    unsafe fn process_name(hwnd: HWND) -> Option<String> {
        let mut pid = 0u32;
        GetWindowThreadProcessId(hwnd, Some(&mut pid));
        let handle = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, false, pid).ok()?;
        let mut buf = [0u16; 520];
        let mut len = buf.len() as u32;
        let ok = QueryFullProcessImageNameW(handle, PROCESS_NAME_WIN32, PWSTR(buf.as_mut_ptr()), &mut len).is_ok();
        let _ = CloseHandle(handle);
        if !ok {
            return None;
        }
        let path = String::from_utf16_lossy(&buf[..len as usize]);
        let file = path.rsplit('\\').next().unwrap_or(&path);
        Some(file.trim_end_matches(".exe").trim_end_matches(".EXE").to_string())
    }

    pub fn idle_secs() -> u64 {
        let mut info = LASTINPUTINFO { cbSize: std::mem::size_of::<LASTINPUTINFO>() as u32, dwTime: 0 };
        unsafe {
            if !GetLastInputInfo(&mut info).as_bool() {
                return 0;
            }
            (GetTickCount().wrapping_sub(info.dwTime) / 1000) as u64
        }
    }

    /// A JPEG of the window in front (`window`) or of the main screen,
    /// scaled down to at most 1400 px wide.
    pub fn capture(window: bool) -> Option<Vec<u8>> {
        unsafe {
            let (x, y, w, h) = if window {
                let mut r = RECT::default();
                GetWindowRect(GetForegroundWindow(), &mut r).ok()?;
                (r.left.max(0), r.top.max(0), (r.right - r.left.max(0)), (r.bottom - r.top.max(0)))
            } else {
                (0, 0, GetSystemMetrics(SM_CXSCREEN), GetSystemMetrics(SM_CYSCREEN))
            };
            if w < 50 || h < 50 {
                return None;
            }
            let screen = GetDC(None);
            let mem = CreateCompatibleDC(Some(screen));
            let bmp = CreateCompatibleBitmap(screen, w, h);
            let old = SelectObject(mem, bmp.into());
            let copied = BitBlt(mem, 0, 0, w, h, Some(screen), x, y, SRCCOPY).is_ok();
            let mut info = BITMAPINFO {
                bmiHeader: BITMAPINFOHEADER {
                    biSize: std::mem::size_of::<BITMAPINFOHEADER>() as u32,
                    biWidth: w,
                    biHeight: -h,
                    biPlanes: 1,
                    biBitCount: 32,
                    biCompression: BI_RGB.0,
                    ..Default::default()
                },
                ..Default::default()
            };
            let mut bgra = vec![0u8; (w * h * 4) as usize];
            let lines = GetDIBits(mem, bmp, 0, h as u32, Some(bgra.as_mut_ptr() as _), &mut info, DIB_RGB_COLORS);
            SelectObject(mem, old);
            let _ = DeleteObject(bmp.into());
            let _ = DeleteDC(mem);
            ReleaseDC(None, screen);
            if !copied || lines == 0 {
                return None;
            }
            super::encode(&bgra, w as usize, h as usize)
        }
    }
}

#[cfg(not(windows))]
mod imp {
    pub fn foreground() -> Option<(String, String)> {
        None
    }
    pub fn idle_secs() -> u64 {
        0
    }
    pub fn capture(_window: bool) -> Option<Vec<u8>> {
        None
    }
}

/// BGRA → scaled RGB → JPEG.
#[allow(dead_code)]
fn encode(bgra: &[u8], w: usize, h: usize) -> Option<Vec<u8>> {
    let scale = (w as f64 / 1400.0).max(1.0);
    let ow = ((w as f64) / scale) as usize;
    let oh = ((h as f64) / scale) as usize;
    let mut rgb = Vec::with_capacity(ow * oh * 3);
    for oy in 0..oh {
        let sy = ((oy as f64) * scale) as usize;
        for ox in 0..ow {
            let sx = ((ox as f64) * scale) as usize;
            let i = (sy * w + sx) * 4;
            rgb.extend_from_slice(&[bgra[i + 2], bgra[i + 1], bgra[i]]);
        }
    }
    let mut out = Vec::new();
    let enc = jpeg_encoder::Encoder::new(&mut out, 72);
    enc.encode(&rgb, ow as u16, oh as u16, jpeg_encoder::ColorType::Rgb).ok()?;
    Some(out)
}
