// Personal build: lock-screen alerts on the phone through ntfy (free, open
// source, on the App Store). Coucou posts to a private topic name; the ntfy app
// on the phone subscribes to the same name. Nothing is sent until a topic is
// set in Settings › Phone.

use std::time::Duration;

use serde_json::json;
use tauri::AppHandle;

use crate::secrets;

/// Seconds since the last mouse or keyboard input on this PC.
#[cfg(windows)]
fn idle_secs() -> u64 {
    use windows::Win32::System::SystemInformation::GetTickCount;
    use windows::Win32::UI::Input::KeyboardAndMouse::{GetLastInputInfo, LASTINPUTINFO};
    let mut info = LASTINPUTINFO { cbSize: std::mem::size_of::<LASTINPUTINFO>() as u32, dwTime: 0 };
    if !unsafe { GetLastInputInfo(&mut info) }.as_bool() {
        return u64::MAX;
    }
    let now = unsafe { GetTickCount() };
    (now.wrapping_sub(info.dwTime) / 1000) as u64
}

#[cfg(not(windows))]
fn idle_secs() -> u64 {
    u64::MAX
}

/// Alerts only go to the phone when nobody has touched the PC for 2 minutes:
/// at the desk, the island already says it.
pub fn send(app: &AppHandle, title: &str, message: &str) {
    if idle_secs() >= 120 {
        send_now(app, title, message);
    }
}

/// An alert ntfy holds and delivers at `at_secs` (Unix time), even if the PC
/// is off by then. ntfy keeps scheduled messages up to 3 days ahead.
pub fn send_at(app: &AppHandle, title: &str, message: &str, at_secs: i64) {
    let Some(topic) = secrets::get("ntfy-topic") else { return };
    let mut body = json!({
        "topic": topic.trim(),
        "title": title,
        "message": message.chars().take(400).collect::<String>(),
        "tags": ["alarm_clock"],
        "delay": at_secs.to_string(),
    });
    if let Some(url) = crate::phone::public_url(app) {
        body["click"] = json!(url);
    }
    tauri::async_runtime::spawn(async move {
        let Ok(client) = reqwest::Client::builder().timeout(Duration::from_secs(10)).build() else { return };
        if let Err(err) = client.post("https://ntfy.sh/").json(&body).send().await {
            crate::log::line(format!("ntfy: {err}"));
        }
    });
}

/// Fire and forget: a failed alert never holds anything up.
pub fn send_now(app: &AppHandle, title: &str, message: &str) {
    let Some(topic) = secrets::get("ntfy-topic") else { return };
    let click = crate::phone::public_url(app);
    let mut body = json!({
        "topic": topic.trim(),
        "title": title,
        "message": message.chars().take(400).collect::<String>(),
        "tags": ["robot"],
    });
    // Tapping the alert opens the phone page, when it's set up.
    if let Some(url) = click {
        body["click"] = json!(url);
    }
    tauri::async_runtime::spawn(async move {
        let Ok(client) = reqwest::Client::builder().timeout(Duration::from_secs(10)).build() else { return };
        if let Err(err) = client.post("https://ntfy.sh/").json(&body).send().await {
            crate::log::line(format!("ntfy: {err}"));
        }
    });
}
