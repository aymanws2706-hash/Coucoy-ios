// Coucou for Windows — app wiring and the commands the island calls.

mod agent;
mod awareness;
mod claude;
mod clip;
mod convert;
mod day;
mod glass;
mod jobs;
mod phone;
mod push;
mod desk;
mod files;
mod hooks;
mod integrations;
mod island;
mod log;
mod pipe;
mod platform;
mod secrets;
mod settings;
mod sysstats;
mod voice;
mod whatsapp;
mod elevation;
mod dropcatch;
mod usage;
mod tools;
mod tray;

use std::process::Command;
use std::sync::atomic::Ordering;
use std::sync::{Arc, Mutex};

use serde::Serialize;
use tauri::{AppHandle, Emitter, Manager, State, WebviewUrl, WebviewWindowBuilder};
use tauri_plugin_autostart::{ManagerExt, MacosLauncher};

use claude::{Chat, ChatContext, ChatReply};
use files::DroppedFile;
use hooks::{HookPreview, HookStatus};
use island::{PollGate, ScreenInfo};
use pipe::Pending;
use settings::Settings;

pub struct Shared {
    pub settings: Mutex<Settings>,
    pub gate: Arc<PollGate>,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BootInfo {
    settings: Settings,
    screen: ScreenInfo,
    version: String,
    hook_path: String,
    /// False where the OS has no global cursor (Wayland): the page then reports
    /// the cursor from its own mouse events.
    cursor_poll: bool,
}

#[tauri::command]
fn boot(app: AppHandle, shared: State<Shared>) -> BootInfo {
    let mut settings = shared.settings.lock().unwrap().clone();
    // The real state of ~/.claude/settings.json wins over whatever we stored.
    settings.hooks_installed = hooks::status().installed;
    let screen = island::screen_info(&app, &settings.screen);
    BootInfo {
        settings,
        screen,
        version: env!("CARGO_PKG_VERSION").to_string(),
        hook_path: settings::hook_exe_path().to_string_lossy().to_string(),
        cursor_poll: platform::CURSOR_POLL,
    }
}

#[tauri::command]
fn save_settings(app: AppHandle, shared: State<Shared>, settings: Settings) {
    let (screen_changed, autostart_changed) = {
        let mut current = shared.settings.lock().unwrap();
        let screen_changed = current.screen != settings.screen;
        let autostart_changed = current.autostart != settings.autostart;
        *current = settings.clone();
        (screen_changed, autostart_changed)
    };
    if let Err(err) = settings::save(&settings) {
        eprintln!("[coucou] could not save settings: {err}");
    }
    if autostart_changed {
        let manager = app.autolaunch();
        let result = if settings.autostart { manager.enable() } else { manager.disable() };
        if let Err(err) = result {
            eprintln!("[coucou] autostart: {err}");
        }
    }
    if screen_changed {
        let collapsed = shared.gate.collapsed.load(Ordering::Relaxed);
        island::apply_geometry(&app, &settings.screen, collapsed);
    }
    // Keep the other window in step (island ⇄ settings window).
    let _ = app.emit("settings-changed", settings);
}

/// Hidden island → shrink the window to the invisible wake strip and park the
/// cursor poll; anything else → full panel and 60 Hz polling.
#[tauri::command]
fn set_collapsed(app: AppHandle, shared: State<Shared>, collapsed: bool) {
    let pref = shared.settings.lock().unwrap().screen.clone();
    shared.gate.collapsed.store(collapsed, Ordering::Relaxed);
    island::apply_geometry(&app, &pref, collapsed);
    // The wake strip must always take the mouse, and a resize invalidates the flag.
    island::refresh_click_through(&app, &shared.gate);
    shared.gate.set_active(!collapsed);
}

/// The front end pushes the island shape; Rust decides click-through from it.
#[tauri::command]
fn set_island_rect(
    app: AppHandle,
    shared: State<Shared>,
    x: f64,
    y: f64,
    width: f64,
    height: f64,
    radius: Option<f64>,
) {
    shared.gate.set_rect(island::IslandRect { x, y, w: width, h: height });
    // Personal build: the glass window follows the island's shape.
    if let Some(win) = island::window(&app) {
        glass::shape(&win, x, y, width, height, radius.unwrap_or(14.0));
    }
    // Without the cursor poll the input region is the click-through: it follows the island.
    if !platform::CURSOR_POLL {
        island::refresh_click_through(&app, &shared.gate);
    }
}

#[tauri::command]
fn focus_window(app: AppHandle, focused: bool) {
    let Some(win) = island::window(&app) else { return };
    platform::set_activating(&win, focused);
    if focused {
        let _ = win.set_focus();
    }
}

#[tauri::command]
fn reposition(app: AppHandle, shared: State<Shared>) {
    let pref = shared.settings.lock().unwrap().screen.clone();
    let collapsed = shared.gate.collapsed.load(Ordering::Relaxed);
    island::apply_geometry(&app, &pref, collapsed);
}

#[tauri::command]
fn open_url(url: String) {
    if !(url.starts_with("http://") || url.starts_with("https://")) {
        return;
    }
    platform::open_url(&url);
}

/// "Open terminal" opens the working folder in VS Code when `code` is on PATH,
/// and falls back to the file manager otherwise.
#[tauri::command]
fn open_in_vscode(path: Option<String>) -> bool {
    // No shell anywhere near this. The path is a project folder chosen by
    // whoever is using Claude Code, and a shell would happily read `&`, `^`, `%`
    // or `$` in a folder name as syntax. Finding the launcher ourselves and
    // handing the path over as a separate argument keeps it a path.
    let path = path.filter(|p| !p.is_empty());
    // It arrives in a hook payload: only an existing folder, given by its full
    // path, goes any further. `code` would read `--something` as an option, and
    // xdg-open would launch a file with whatever handles its type.
    if let Some(p) = path.as_deref() {
        let p = std::path::Path::new(p);
        if !(p.is_absolute() && p.is_dir()) {
            return false;
        }
    }
    if let Some(code) = platform::find_on_path("code") {
        let mut cmd = Command::new(code);
        if let Some(p) = path.as_deref() {
            cmd.arg(p);
        }
        if platform::no_console(&mut cmd).spawn().is_ok() {
            return true;
        }
    }
    if let Some(p) = path.as_deref() {
        platform::reveal_folder(p);
    }
    false
}

#[tauri::command]
fn quit_app(app: AppHandle) {
    app.exit(0);
}

/// Weather where you are (or in the city set in Settings), cached 15 min.
#[tauri::command]
async fn weather(day: State<'_, day::Day>, force: bool) -> Result<day::Weather, String> {
    day.weather(force).await
}

/// The next week of events from the calendar's private iCal link.
#[tauri::command]
async fn calendar(day: State<'_, day::Day>, force: bool) -> Result<Vec<day::Event>, String> {
    day.calendar(force).await
}

// ── Controls panel (personal build) ─────────────────────────────────────────
// Every one of these talks to Windows synchronously, so each runs on a
// blocking thread rather than the window's.

async fn blocking<T: Send + 'static>(f: impl FnOnce() -> T + Send + 'static) -> Result<T, String> {
    tauri::async_runtime::spawn_blocking(f).await.map_err(|e| e.to_string())
}

#[tauri::command]
async fn now_playing() -> Result<Option<desk::NowPlaying>, String> {
    blocking(desk::now_playing).await
}

#[tauri::command]
async fn media_control(action: String) -> Result<(), String> {
    blocking(move || desk::media(&action)).await?
}

#[tauri::command]
async fn desk_controls(brightness: bool) -> Result<desk::Controls, String> {
    blocking(move || desk::controls(brightness)).await
}

#[tauri::command]
async fn set_volume(percent: u8) -> Result<(), String> {
    blocking(move || desk::set_volume(percent)).await?
}

#[tauri::command]
async fn set_mute(mic: bool, muted: bool) -> Result<(), String> {
    blocking(move || desk::set_mute(mic, muted)).await?
}

#[tauri::command]
async fn set_brightness(percent: u8) -> Result<(), String> {
    blocking(move || desk::set_brightness(percent)).await?
}

#[tauri::command]
async fn desk_activity() -> Result<desk::Activity, String> {
    blocking(desk::activity).await
}

#[tauri::command]
async fn shortcut(which: String) -> Result<(), String> {
    blocking(move || desk::shortcut(&which)).await?
}

#[tauri::command]
fn clipboard_history(history: State<clip::History>) -> Vec<String> {
    history.0.lock().unwrap().clone()
}

#[tauri::command]
fn clipboard_copy(app: AppHandle, index: usize) -> Result<(), String> {
    clip::copy(&app, index)
}

#[tauri::command]
fn clipboard_clear(history: State<clip::History>) {
    history.0.lock().unwrap().clear();
}

// ── Phone link (personal build) ─────────────────────────────────────────────

#[tauri::command]
async fn phone_info(app: AppHandle) -> Result<phone::PhoneInfo, String> {
    blocking(move || phone::info(&app)).await
}

#[tauri::command]
async fn phone_enable(app: AppHandle) -> Result<phone::PhoneInfo, String> {
    blocking(move || phone::enable(&app)).await?
}

#[tauri::command]
async fn phone_disable(app: AppHandle) -> Result<(), String> {
    blocking(move || phone::disable(&app)).await?
}

/// The island's timer / Claude Code state, for the phone page.
#[tauri::command]
fn phone_publish(app: AppHandle, snapshot: serde_json::Value) {
    phone::publish(&app, snapshot);
}

/// An alert to the phone through ntfy (timer done, Claude Code, PC health),
/// only when the PC has been left alone; `now` skips that check (the test button).
#[tauri::command]
fn push_notify(app: AppHandle, title: String, message: String, now: Option<bool>) {
    if now.unwrap_or(false) {
        push::send_now(&app, &title, &message);
    } else {
        push::send(&app, &title, &message);
    }
}

#[tauri::command]
fn awareness_get(aw: State<awareness::Awareness>) -> awareness::Config {
    aw.config()
}

#[tauri::command]
fn awareness_set(aw: State<awareness::Awareness>, config: awareness::Config) -> Result<(), String> {
    aw.set_config(config)
}

/// Accepting a suggestion (or any reminder from the island): notch at the
/// time, plus a scheduled phone alert.
#[tauri::command]
fn add_reminder(app: AppHandle, text: String, at: i64) {
    let _ = app.emit("reminder", serde_json::json!({ "at": at, "text": text }));
    push::send_at(&app, "⏰ Reminder", &text, at / 1000);
}

/// "2026-10-16T18:30" in local time → epoch ms (for suggestions' times).
#[tauri::command]
fn local_time_ms(text: String) -> Option<i64> {
    day::local_to_epoch_ms(&text)
}

// ── Convert (personal build) ─────────────────────────────────────────────────

#[tauri::command]
fn convert_targets(path: String) -> Vec<convert::Target> {
    convert::targets(&path)
}

/// Returns the new file's path. "NEEDS_FFMPEG" means: offer to install it.
#[tauri::command]
async fn convert_file(path: String, to: String) -> Result<String, String> {
    blocking(move || convert::convert(&path, &to)).await?
}

#[tauri::command]
async fn install_ffmpeg() -> Result<(), String> {
    blocking(convert::install_ffmpeg).await?
}

/// Opens a file with its usual app, or shows it selected in Explorer.
#[tauri::command]
fn open_file(path: String, reveal: bool) {
    #[cfg(windows)]
    {
        let mut cmd = Command::new(if reveal { "explorer" } else { "cmd" });
        if reveal {
            cmd.arg(format!("/select,{path}"));
        } else {
            cmd.args(["/C", "start", "", &path]);
        }
        platform::no_console(&mut cmd);
        let _ = cmd.spawn();
    }
    #[cfg(not(windows))]
    {
        let target = if reveal {
            std::path::Path::new(&path).parent().map(|p| p.display().to_string()).unwrap_or(path)
        } else {
            path
        };
        let _ = Command::new("xdg-open").arg(target).spawn();
    }
}

/// Liquid Glass blur behind the island (Windows acrylic). Returns whether it took.
#[tauri::command]
fn set_glass(app: AppHandle, on: bool) -> bool {
    island::window(&app).map(|w| glass::set_enabled(&w, on)).unwrap_or(false)
}

/// Allow / Deny on a card Mochi's own chat raised (not a Claude Code one).
#[tauri::command]
fn mochi_decision(approvals: State<agent::Approvals>, id: u64, allow: bool) {
    approvals.decide(id, allow);
}

/// Presses Win+H so Windows voice typing fills the focused chat field.
#[tauri::command]
fn start_dictation() -> Result<(), String> {
    voice::start_dictation()
}

/// The apps using the most CPU and memory, for the PC health list.
#[tauri::command]
async fn top_apps(stats: State<'_, sysstats::Stats>) -> Result<Vec<sysstats::AppUsage>, String> {
    Ok(stats.top_processes(6))
}

/// The ✕ next to an app in the PC health list; the island asks first.
#[tauri::command]
async fn kill_app(stats: State<'_, sysstats::Stats>, name: String) -> Result<usize, String> {
    Ok(stats.kill_app(&name))
}

/// CPU, memory, disk, network, battery and uptime for the notch and the PC view.
/// Async so the sampling never runs on the window's thread.
#[tauri::command]
async fn system_stats(stats: State<'_, sysstats::Stats>) -> Result<sysstats::SystemStats, String> {
    Ok(stats.sample())
}

/// Tray → Pause. Paused means paused: the pollers stop talking to the network,
/// not just the island stopping showing things.
#[tauri::command]
fn set_paused(paused: bool) {
    integrations::set_paused(paused);
}

// ── Claude Code hooks ─────────────────────────────────────────────────────────

#[tauri::command]
fn hooks_status() -> HookStatus {
    hooks::status()
}

/// Returns the diff the user has to look at before anything is written.
#[tauri::command]
fn hooks_preview(install: bool) -> Result<HookPreview, String> {
    hooks::preview(install)
}

/// Only ever called from an explicit click in the settings window.
#[tauri::command]
fn hooks_apply(
    app: AppHandle,
    shared: State<Shared>,
    install: bool,
    fingerprint: String,
) -> Result<String, String> {
    // The fingerprint comes from the preview the user actually looked at, so a
    // settings.json that changed in between is refused rather than overwritten.
    let backup = hooks::write(install, &fingerprint)?;
    let updated = {
        let mut current = shared.settings.lock().unwrap();
        current.hooks_installed = install;
        let _ = settings::save(&current);
        current.clone()
    };
    let _ = app.emit("settings-changed", updated);
    Ok(backup)
}

#[tauri::command]
fn approval_decision(app: AppHandle, request_id: String, decision: String) {
    pipe::answer(&app, &request_id, &decision);
}

/// The island has the card on screen, so the long wait for a human may begin.
/// Until this arrives the relay only waits a few hundred milliseconds, which is
/// what stops a paused or unresponsive island from freezing Claude Code.
#[tauri::command]
fn approval_ack(app: AppHandle, request_id: String) {
    pipe::acknowledge(&app, &request_id);
}

/// Nobody can act on this request — the island is paused, or another card is
/// already up. Claude Code falls back to asking in the terminal immediately.
#[tauri::command]
fn approval_decline(app: AppHandle, request_id: String) {
    pipe::decline(&app, &request_id);
}

// ── Chat, files and secrets ───────────────────────────────────────────────────

/// One chat turn. The API key and any file bytes stay on the Rust side.
#[tauri::command]
async fn chat_send(
    app: AppHandle,
    shared: State<'_, Shared>,
    chat: State<'_, Chat>,
    query: String,
    context: Option<ChatContext>,
) -> Result<ChatReply, String> {
    let model = shared.settings.lock().unwrap().model.clone();
    claude::send(&app, &chat, &model, query, context).await
}

#[tauri::command]
fn chat_reset(chat: State<Chat>) {
    chat.reset();
}

/// Copies a dropped file into the inbox and reports its name back.
#[tauri::command]
fn ingest_file(path: String) -> Result<DroppedFile, String> {
    files::ingest(&path)
}

/// The island may only ask whether a key exists — never read it.
#[tauri::command]
fn secret_present(key: String) -> bool {
    secrets::present(&key)
}

#[tauri::command]
fn secret_set(key: String, value: String) -> Result<(), String> {
    secrets::set(&key, &value)
}

#[tauri::command]
fn secret_clear(key: String) -> Result<(), String> {
    secrets::clear(&key)
}

/// Opens the configured n8n instance — the URL lives in the Credential Manager.
#[tauri::command]
fn open_n8n() {
    if let Some(url) = secrets::get("n8n-url") {
        open_url(url);
    }
}

/// Refresh buttons in the integration cards.
#[tauri::command]
async fn refresh_integration(app: AppHandle, id: String) {
    integrations::poll_once(app, &id).await;
}

/// Lets the island write to the same log as the Rust side.
#[tauri::command]
fn log_line(message: String) {
    log::line(format!("ui  {message}"));
}

// ── Settings window ───────────────────────────────────────────────────────────

/// WebView2 allows exactly one browser environment per app, and its options are
/// fixed by whichever webview is created first. Every window must therefore ask
/// for the *same* arguments as the island (see `additionalBrowserArgs` in
/// tauri.conf.json) — a mismatch makes the second window come up blank, with no
/// error anywhere.
const BROWSER_ARGS: &str = "--disable-features=msWebOOUI,msPdfOOUI,msSmartScreenProtection --autoplay-policy=no-user-gesture-required";

/// In a dev build the pages are served by Vite, so the second window needs the
/// absolute dev URL; a bundled build resolves it inside the app bundle.
fn settings_page_url(app: &AppHandle) -> WebviewUrl {
    #[cfg(dev)]
    if let Some(mut base) = app.config().build.dev_url.clone() {
        base.set_path("/settings.html");
        return WebviewUrl::External(base);
    }
    let _ = app;
    WebviewUrl::App("settings.html".into())
}

/// The settings window is created hidden at launch and only ever shown and
/// hidden afterwards. A WebView2 window created later — on the main thread or
/// not — silently comes up blank in this app, so the window that works is the
/// one that exists before the island's webview does.
fn create_settings_window(app: &AppHandle) {
    let url = settings_page_url(app);
    match WebviewWindowBuilder::new(app, "settings", url)
        .additional_browser_args(BROWSER_ARGS)
        .title("Settings — Coucou")
        .inner_size(560.0, 680.0)
        .min_inner_size(460.0, 480.0)
        .resizable(true)
        .visible(false)
        .center()
        .build()
    {
        Ok(win) => {
            // Closing it must only hide it, or it could never be reopened.
            let hidden = win.clone();
            win.on_window_event(move |event| {
                if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                    api.prevent_close();
                    let _ = hidden.hide();
                }
            });
        }
        Err(err) => log::line(format!("settings window failed: {err}")),
    }
}

pub fn show_settings_window(app: &AppHandle) {
    let Some(win) = app.get_webview_window("settings") else {
        log::line("settings window missing");
        return;
    };
    let _ = win.unminimize();
    let _ = win.center();
    let _ = win.show();
    let _ = win.set_focus();
}

#[tauri::command]
fn open_settings_window(app: AppHandle) {
    show_settings_window(&app);
}

/// Personal build: today's time per app and Revit project, for the evening recap.
#[tauri::command]
fn usage_today(usage: State<usage::Usage>) -> usage::Day {
    usage.today()
}

/// Personal build: seconds since the last input (morning briefing waits for you).
#[tauri::command]
fn idle_secs() -> u64 {
    awareness::idle_secs()
}

/// Personal build: recent WhatsApp messages for the briefing, if reading is on.
#[tauri::command]
fn whatsapp_recent(app: AppHandle) -> Option<Vec<whatsapp::Message>> {
    if !app.state::<awareness::Awareness>().config().whatsapp {
        return None;
    }
    app.state::<whatsapp::WhatsApp>().recent().ok()
}

/// Personal build: synced lyrics from lrclib.net for the notch.
#[tauri::command]
async fn lyrics(artist: String, title: String, duration: f64) -> Option<Vec<(f64, String)>> {
    desk::lyrics(&artist, &title, duration).await
}

/// Personal build: likes the song playing in Spotify (its Alt+Shift+B shortcut).
#[tauri::command]
async fn spotify_like() -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(desk::spotify_like).await.map_err(|e| e.to_string())?
}

// ── Personal build: file tools, translate, screenshots ──────────────────────

#[tauri::command]
async fn translate_text(text: String, to: String) -> Result<String, String> {
    tools::translate_text(&text, &to).await
}

#[tauri::command]
async fn translate_file(path: String, to: String) -> Result<String, String> {
    tools::translate_file(&path, &to).await
}

#[tauri::command]
async fn summarize_file(path: String) -> Result<String, String> {
    tools::summarize_file(&path).await
}

#[tauri::command]
async fn resize_image(path: String, max: u32) -> Result<String, String> {
    tauri::async_runtime::spawn_blocking(move || tools::resize_image(&path, max)).await.map_err(|e| e.to_string())?
}

#[tauri::command]
async fn compress_pdf(path: String) -> Result<String, String> {
    tauri::async_runtime::spawn_blocking(move || tools::compress_pdf(&path)).await.map_err(|e| e.to_string())?
}

#[tauri::command]
async fn install_ghostscript() -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(tools::install_ghostscript).await.map_err(|e| e.to_string())?
}

#[tauri::command]
async fn merge_pdfs(paths: Vec<String>) -> Result<String, String> {
    tauri::async_runtime::spawn_blocking(move || tools::merge_pdfs(&paths)).await.map_err(|e| e.to_string())?
}

#[tauri::command]
async fn ocr_image(path: String) -> Result<String, String> {
    tauri::async_runtime::spawn_blocking(move || tools::ocr(&path)).await.map_err(|e| e.to_string())?
}

#[tauri::command]
fn start_snip(app: AppHandle) {
    tools::start_snip(&app);
}

#[tauri::command]
fn copy_text(app: AppHandle, text: String) -> Result<(), String> {
    use tauri_plugin_clipboard_manager::ClipboardExt;
    app.clipboard().write_text(text).map_err(|e| e.to_string())
}

/// Personal build: the Windows file dialog, for when dragging a file in isn't possible.
#[tauri::command]
async fn pick_file() -> Option<String> {
    tauri::async_runtime::spawn_blocking(elevation::pick_file).await.ok().flatten()
}

pub fn run() {
    // Personal build: started as administrator (e.g. by the installer), Windows
    // blocks files dragged in from Explorer. Start again as the normal user.
    if elevation::relaunch_unelevated() {
        return;
    }
    platform::prepare_environment();
    let loaded = settings::load();
    let gate = Arc::new(PollGate::new());

    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| {
            let _ = app.emit_to(island::WINDOW_LABEL, "tray", "open".to_string());
        }))
        .plugin(tauri_plugin_autostart::init(MacosLauncher::LaunchAgent, None))
        .plugin(tauri_plugin_clipboard_manager::init())
        // Personal build: Ctrl+Shift+Space opens the chat from anywhere.
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_handler(|app, shortcut, event| {
                    use tauri_plugin_global_shortcut::{Code, Modifiers};
                    if event.state() != tauri_plugin_global_shortcut::ShortcutState::Pressed {
                        return;
                    }
                    let ctrl_alt = Modifiers::CONTROL | Modifiers::ALT;
                    if shortcut.matches(ctrl_alt, Code::KeyS) {
                        // Ctrl+Alt+S: Windows' snipping bar, then the snip card.
                        tools::start_snip(app);
                    } else if shortcut.matches(ctrl_alt, Code::KeyT) {
                        // Ctrl+Alt+T: translate whatever is selected.
                        let app = app.clone();
                        std::thread::spawn(move || {
                            let text = tools::copy_selection(&app).unwrap_or_default();
                            let _ = app.emit("translate-selection", text);
                        });
                    } else {
                        let _ = app.emit("hotkey", "chat");
                    }
                })
                .build(),
        )
        .manage(Shared {
            settings: Mutex::new(loaded.clone()),
            gate: gate.clone(),
        })
        .manage(Pending::default())
        .manage(Chat::default())
        .manage(sysstats::Stats::default())
        .manage(agent::Approvals::default())
        .manage(day::Day::default())
        .manage(clip::History::default())
        .manage(phone::Phone::default())
        .manage(jobs::Jobs::default())
        .manage(awareness::Awareness::default())
        .manage(whatsapp::WhatsApp::default())
        .manage(usage::Usage::default())
        .invoke_handler(tauri::generate_handler![
            boot,
            save_settings,
            set_collapsed,
            set_island_rect,
            focus_window,
            reposition,
            open_url,
            open_in_vscode,
            quit_app,
            hooks_status,
            hooks_preview,
            hooks_apply,
            approval_decision,
            approval_ack,
            approval_decline,
            log_line,
            chat_send,
            chat_reset,
            ingest_file,
            secret_present,
            secret_set,
            secret_clear,
            refresh_integration,
            open_n8n,
            open_settings_window,
            set_paused,
            system_stats,
            mochi_decision,
            start_dictation,
            top_apps,
            kill_app,
            weather,
            calendar,
            now_playing,
            media_control,
            desk_controls,
            set_volume,
            set_mute,
            set_brightness,
            desk_activity,
            shortcut,
            clipboard_history,
            clipboard_copy,
            clipboard_clear,
            phone_info,
            phone_enable,
            phone_disable,
            phone_publish,
            push_notify,
            set_glass,
            awareness_get,
            pick_file,
            translate_text,
            translate_file,
            summarize_file,
            resize_image,
            compress_pdf,
            install_ghostscript,
            merge_pdfs,
            ocr_image,
            start_snip,
            copy_text,
            usage_today,
            idle_secs,
            whatsapp_recent,
            lyrics,
            spotify_like,
            awareness_set,
            add_reminder,
            local_time_ms,
            convert_targets,
            convert_file,
            install_ffmpeg,
            open_file,
        ])
        .setup(move |app| {
            let handle = app.handle().clone();
            tray::build(&handle)?;
            clip::watch(handle.clone());
            // Tasks left from the phone: watch for new ones, run them when due.
            jobs::start(handle.clone());
            // Awareness: does nothing until switched on in Settings.
            awareness::start(handle.clone());
            // Dropped files, the classic way, for when the webview refuses them.
            dropcatch::start(&handle);
            usage::start(handle.clone());
            // The phone link comes back on by itself once it has been paired.
            if phone::token().is_some() {
                phone::start(handle.clone());
            }
            {
                use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut};
                let chat_key = Shortcut::new(Some(Modifiers::CONTROL | Modifiers::SHIFT), Code::Space);
                if let Err(err) = handle.global_shortcut().register(chat_key) {
                    log::line(&format!("hotkey Ctrl+Shift+Space not available: {err}"));
                }
                for (code, name) in [(Code::KeyS, "Ctrl+Alt+S"), (Code::KeyT, "Ctrl+Alt+T")] {
                    let key = Shortcut::new(Some(Modifiers::CONTROL | Modifiers::ALT), code);
                    if let Err(err) = handle.global_shortcut().register(key) {
                        log::line(&format!("hotkey {name} not available: {err}"));
                    }
                }
            }
            // Before the island: see create_settings_window.
            create_settings_window(&handle);

            if let Some(win) = island::window(&handle) {
                platform::make_non_activating(&win);
                island::apply_geometry(&handle, &loaded.screen, false);
                let _ = win.show();
            }
            gate.collapsed.store(false, Ordering::Relaxed);
            // Nothing drawn yet, so nothing takes the mouse until the page
            // reports the island's shape.
            if !platform::CURSOR_POLL {
                island::refresh_click_through(&handle, &gate);
            }
            gate.set_active(true);
            island::spawn_cursor_poll(handle.clone(), gate.clone());

            log::line(format!("--- Coucou {} started ---", env!("CARGO_PKG_VERSION")));
            hooks::ensure_hook_exe(&handle);
            pipe::start(handle.clone());
            integrations::start(handle.clone());
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running Coucou");
}
