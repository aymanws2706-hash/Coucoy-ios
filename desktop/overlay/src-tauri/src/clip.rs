// Personal build: the last few things copied, in memory only — never written
// to disk, gone when Coucou quits, and clearable from the island. A cheap
// sequence number tells us when something new was copied, so the clipboard
// itself is only opened when it actually changed.

use std::sync::Mutex;
use std::time::Duration;

use tauri::{AppHandle, Manager};
use tauri_plugin_clipboard_manager::ClipboardExt;

const KEEP: usize = 8;
const MAX_CHARS: usize = 20_000;

#[derive(Default)]
pub struct History(pub Mutex<Vec<String>>);

/// Watches the clipboard for the life of the app.
pub fn watch(app: AppHandle) {
    std::thread::spawn(move || {
        let mut last = crate::desk::clipboard_seq();
        loop {
            std::thread::sleep(Duration::from_millis(1200));
            let seq = crate::desk::clipboard_seq();
            if seq == last {
                continue;
            }
            last = seq;
            let Ok(text) = app.clipboard().read_text() else { continue };
            if text.trim().is_empty() || text.chars().count() > MAX_CHARS {
                continue;
            }
            let history = app.state::<History>();
            let mut items = history.0.lock().unwrap();
            items.retain(|t| t != &text);
            items.insert(0, text);
            items.truncate(KEEP);
        }
    });
}

pub fn copy(app: &AppHandle, index: usize) -> Result<(), String> {
    let text = {
        let history = app.state::<History>();
        let items = history.0.lock().unwrap();
        items.get(index).cloned().ok_or("That item is gone.")?
    };
    app.clipboard().write_text(text).map_err(|e| e.to_string())
}
