// Personal build: desktop controls for the Controls panel and the notch —
// now playing (any app that shows in Windows' media flyout), volume and mic
// mute, screen brightness (laptops), Wi-Fi, mic / camera in use, downloads in
// progress, clipboard history and a few shortcuts.
//
// Everything Windows-specific is in `win`; Linux gets harmless stand-ins so the
// rest of the app builds unchanged.

use serde::Serialize;

#[derive(Serialize, Clone, Default)]
#[serde(rename_all = "camelCase")]
pub struct NowPlaying {
    pub title: String,
    pub artist: String,
    /// The app playing it, e.g. "Spotify" or "chrome".
    pub app: String,
    pub playing: bool,
    /// Seconds; 0 when the app doesn't say.
    pub position: f64,
    pub duration: f64,
    /// The album art's main colour, "#rrggbb", for the notch glow.
    pub color: Option<String>,
    /// The album art, small, as a data: URL.
    pub art: Option<String>,
}

#[derive(Serialize, Clone, Default)]
#[serde(rename_all = "camelCase")]
pub struct Controls {
    /// 0–100, None when there is no output device.
    pub volume: Option<u8>,
    pub muted: bool,
    pub mic_muted: Option<bool>,
    /// 0–100, None on screens Windows can't dim (most desktop monitors).
    pub brightness: Option<u8>,
    pub wifi: Option<String>,
    pub wifi_signal: Option<u8>,
}

#[derive(Serialize, Clone, Default)]
#[serde(rename_all = "camelCase")]
pub struct Activity {
    pub mic_in_use: bool,
    pub camera_in_use: bool,
    /// Files still downloading in the Downloads folder.
    pub downloads: Vec<Download>,
}

#[derive(Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct Download {
    pub name: String,
    pub bytes: u64,
}

/// Downloads in progress: browsers write to a temporary name until the file
/// is complete (.crdownload for Chrome/Edge, .part for Firefox).
pub fn downloads() -> Vec<Download> {
    let dir = crate::platform::home_dir().join("Downloads");
    let Ok(entries) = std::fs::read_dir(dir) else { return Vec::new() };
    let mut out: Vec<Download> = entries
        .flatten()
        .filter_map(|e| {
            let name = e.file_name().to_string_lossy().to_string();
            let lower = name.to_lowercase();
            let real = [".crdownload", ".part", ".partial", ".download"]
                .iter()
                .find_map(|ext| lower.strip_suffix(ext).map(|_| name[..name.len() - ext.len()].to_string()))?;
            let bytes = e.metadata().ok()?.len();
            // Chrome names an unconfirmed download "Unconfirmed 12345".
            Some(Download { name: if real.is_empty() { name } else { real }, bytes })
        })
        .collect();
    out.sort_by(|a, b| b.bytes.cmp(&a.bytes));
    out.truncate(3);
    out
}

/// The main colour of a picture (skips greys so a white border doesn't win),
/// and a 96 px JPEG copy as a data: URL.
pub fn art_summary(bytes: &[u8]) -> Option<(String, String)> {
    let img = image::load_from_memory(bytes).ok()?;
    let small = img.thumbnail(32, 32).to_rgb8();
    let (mut r, mut g, mut b, mut n) = (0f64, 0f64, 0f64, 0f64);
    let (mut ar, mut ag, mut ab) = (0f64, 0f64, 0f64);
    for p in small.pixels() {
        let [pr, pg, pb] = p.0.map(|c| c as f64);
        ar += pr;
        ag += pg;
        ab += pb;
        let max = pr.max(pg).max(pb);
        let min = pr.min(pg).min(pb);
        let sat = if max > 0.0 { (max - min) / max } else { 0.0 };
        if sat > 0.25 && max > 50.0 {
            let w = sat * sat;
            r += pr * w;
            g += pg * w;
            b += pb * w;
            n += w;
        }
    }
    let count = (small.width() * small.height()).max(1) as f64;
    let (r, g, b) = if n > 0.5 { (r / n, g / n, b / n) } else { (ar / count, ag / count, ab / count) };
    let color = format!("#{:02x}{:02x}{:02x}", r as u8, g as u8, b as u8);
    let mut jpeg = Vec::new();
    img.thumbnail(96, 96)
        .to_rgb8()
        .write_to(&mut std::io::Cursor::new(&mut jpeg), image::ImageFormat::Jpeg)
        .ok()?;
    Some((color, format!("data:image/jpeg;base64,{}", crate::claude::base64_for(&jpeg))))
}

/// Synced lyrics from lrclib.net (free, no account): (seconds, line).
pub async fn lyrics(artist: &str, title: &str, duration: f64) -> Option<Vec<(f64, String)>> {
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(8))
        .user_agent("Putshi (personal build of Coucou)")
        .build()
        .ok()?;
    let mut req = client.get("https://lrclib.net/api/get").query(&[("artist_name", artist), ("track_name", title)]);
    if duration > 0.0 {
        req = req.query(&[("duration", format!("{}", duration.round() as u64))]);
    }
    let mut v: serde_json::Value = req.send().await.ok()?.json().await.ok()?;
    if v.get("syncedLyrics").and_then(|s| s.as_str()).is_none() {
        // Not found with the exact length: search instead.
        let list: Vec<serde_json::Value> = client
            .get("https://lrclib.net/api/search")
            .query(&[("artist_name", artist), ("track_name", title)])
            .send()
            .await
            .ok()?
            .json()
            .await
            .ok()?;
        v = list.into_iter().find(|x| x.get("syncedLyrics").and_then(|s| s.as_str()).is_some())?;
    }
    let text = v.get("syncedLyrics")?.as_str()?;
    Some(parse_lrc(text))
}

/// "[01:02.34] line" → (62.34, "line").
pub fn parse_lrc(text: &str) -> Vec<(f64, String)> {
    let mut out = Vec::new();
    for line in text.lines() {
        let Some(rest) = line.strip_prefix('[') else { continue };
        let Some((stamp, words)) = rest.split_once(']') else { continue };
        let Some((m, s)) = stamp.split_once(':') else { continue };
        let (Ok(m), Ok(s)) = (m.trim().parse::<f64>(), s.trim().parse::<f64>()) else { continue };
        out.push((m * 60.0 + s, words.trim().to_string()));
    }
    out
}

#[cfg(windows)]
pub use win::*;

#[cfg(windows)]
mod win {
    use super::*;
    use std::process::Command;

    use windows::Media::Control::{
        GlobalSystemMediaTransportControlsSessionManager as Manager,
        GlobalSystemMediaTransportControlsSessionPlaybackStatus as Status,
    };
    use windows::Win32::Media::Audio::Endpoints::IAudioEndpointVolume;
    use windows::Win32::Media::Audio::{eCapture, eConsole, eRender, IMMDeviceEnumerator, MMDeviceEnumerator};
    use windows::Win32::System::Com::{CoCreateInstance, CoInitializeEx, CLSCTX_ALL, COINIT_MULTITHREADED};

    use crate::platform;

    fn com() {
        // Each call may land on a fresh worker thread; joining the MTA twice is fine.
        let _ = unsafe { CoInitializeEx(None, COINIT_MULTITHREADED) };
    }

    // ── Now playing ──────────────────────────────────────────────────────────

    fn session() -> Option<windows::Media::Control::GlobalSystemMediaTransportControlsSession> {
        com();
        let manager = Manager::RequestAsync().ok()?.get().ok()?;
        manager.GetCurrentSession().ok()
    }

    pub fn now_playing() -> Option<NowPlaying> {
        let s = session()?;
        let props = s.TryGetMediaPropertiesAsync().ok()?.get().ok()?;
        let title = props.Title().map(|t| t.to_string()).unwrap_or_default();
        if title.is_empty() {
            return None;
        }
        let artist = props.Artist().map(|t| t.to_string()).unwrap_or_default();
        let playing = s
            .GetPlaybackInfo()
            .and_then(|i| i.PlaybackStatus())
            .map(|st| st == Status::Playing)
            .unwrap_or(false);
        let (position, duration) = s
            .GetTimelineProperties()
            .map(|t| {
                let pos = t.Position().map(|d| d.Duration as f64 / 1e7).unwrap_or(0.0);
                let end = t.EndTime().map(|d| d.Duration as f64 / 1e7).unwrap_or(0.0);
                (pos, end)
            })
            .unwrap_or((0.0, 0.0));
        let app = s
            .SourceAppUserModelId()
            .map(|a| {
                let a = a.to_string();
                let a = a.rsplit(['\\', '!']).next().unwrap_or(&a).to_string();
                a.trim_end_matches(".exe").to_string()
            })
            .unwrap_or_default();
        let key = format!("{title}\u{1}{artist}");
        let (color, art) = {
            let cached = ART.lock().unwrap().clone();
            match cached {
                Some((k, c, a)) if k == key => (c, a),
                _ => {
                    let got = thumbnail(&props).and_then(|b| art_summary(&b));
                    let (c, a) = got.map(|(c, a)| (Some(c), Some(a))).unwrap_or((None, None));
                    *ART.lock().unwrap() = Some((key, c.clone(), a.clone()));
                    (c, a)
                }
            }
        };
        Some(NowPlaying { title, artist, app, playing, position, duration, color, art })
    }

    /// The last song's art, so it's read once per song, not every 2 s.
    static ART: std::sync::Mutex<Option<(String, Option<String>, Option<String>)>> = std::sync::Mutex::new(None);

    fn thumbnail(props: &windows::Media::Control::GlobalSystemMediaTransportControlsSessionMediaProperties) -> Option<Vec<u8>> {
        use windows::Storage::Streams::DataReader;
        let stream = props.Thumbnail().ok()?.OpenReadAsync().ok()?.get().ok()?;
        let size = stream.Size().ok()? as u32;
        if size == 0 || size > 8_000_000 {
            return None;
        }
        let reader = DataReader::CreateDataReader(&stream.GetInputStreamAt(0).ok()?).ok()?;
        reader.LoadAsync(size).ok()?.get().ok()?;
        let mut buf = vec![0u8; size as usize];
        reader.ReadBytes(&mut buf).ok()?;
        Some(buf)
    }

    /// Likes the current song in Spotify through its own shortcut, Alt+Shift+B:
    /// brings Spotify's window forward for a moment, then gives the focus back.
    pub fn spotify_like() -> Result<(), String> {
        use windows::Win32::Foundation::{HWND, LPARAM};
        use windows::Win32::UI::Input::KeyboardAndMouse::{
            SendInput, INPUT, INPUT_0, INPUT_KEYBOARD, KEYBDINPUT, KEYEVENTF_KEYUP, VIRTUAL_KEY, VK_MENU, VK_SHIFT,
        };
        use windows::Win32::UI::WindowsAndMessaging::{
            EnumWindows, GetForegroundWindow, GetWindowTextLengthW, GetWindowThreadProcessId, IsIconic,
            IsWindowVisible, SetForegroundWindow, ShowWindow, SW_RESTORE,
        };

        let pids: Vec<u32> = {
            let mut sys = sysinfo::System::new();
            sys.refresh_processes(sysinfo::ProcessesToUpdate::All, true);
            sys.processes()
                .values()
                .filter(|p| p.name().to_string_lossy().eq_ignore_ascii_case("Spotify.exe"))
                .map(|p| p.pid().as_u32())
                .collect()
        };
        if pids.is_empty() {
            return Err("Spotify isn't open.".into());
        }
        struct Find {
            pids: Vec<u32>,
            found: isize,
        }
        unsafe extern "system" fn each(hwnd: HWND, lp: LPARAM) -> windows::core::BOOL {
            let f = unsafe { &mut *(lp.0 as *mut Find) };
            let mut pid = 0u32;
            unsafe { GetWindowThreadProcessId(hwnd, Some(&mut pid)) };
            if f.pids.contains(&pid) && unsafe { IsWindowVisible(hwnd) }.as_bool() && unsafe { GetWindowTextLengthW(hwnd) } > 0 {
                f.found = hwnd.0 as isize;
                return false.into();
            }
            true.into()
        }
        let mut f = Find { pids, found: 0 };
        unsafe {
            let _ = EnumWindows(Some(each), LPARAM(&mut f as *mut Find as isize));
        }
        if f.found == 0 {
            return Err("Spotify's window is closed (it's only in the tray). Open it once, then try again.".into());
        }
        let spotify = HWND(f.found as *mut _);
        let key = |vk: VIRTUAL_KEY, up: bool| INPUT {
            r#type: INPUT_KEYBOARD,
            Anonymous: INPUT_0 {
                ki: KEYBDINPUT { wVk: vk, dwFlags: if up { KEYEVENTF_KEYUP } else { Default::default() }, ..Default::default() },
            },
        };
        unsafe {
            let previous = GetForegroundWindow();
            // Holding Alt lets this app hand the focus to another window.
            SendInput(&[key(VK_MENU, false)], std::mem::size_of::<INPUT>() as i32);
            if IsIconic(spotify).as_bool() {
                let _ = ShowWindow(spotify, SW_RESTORE);
            }
            let _ = SetForegroundWindow(spotify);
            std::thread::sleep(std::time::Duration::from_millis(180));
            let b = VIRTUAL_KEY(b'B' as u16);
            SendInput(&[key(VK_SHIFT, false), key(b, false), key(b, true), key(VK_SHIFT, true)], std::mem::size_of::<INPUT>() as i32);
            SendInput(&[key(VK_MENU, true)], std::mem::size_of::<INPUT>() as i32);
            std::thread::sleep(std::time::Duration::from_millis(150));
            if !previous.0.is_null() {
                let _ = SetForegroundWindow(previous);
            }
        }
        Ok(())
    }

    /// "toggle", "next" or "previous".
    pub fn media(action: &str) -> Result<(), String> {
        let s = session().ok_or("Nothing is playing.")?;
        let op = match action {
            "next" => s.TrySkipNextAsync(),
            "previous" => s.TrySkipPreviousAsync(),
            _ => s.TryTogglePlayPauseAsync(),
        };
        op.and_then(|o| o.get()).map(|_| ()).map_err(|e| e.message().to_string())
    }

    // ── Volume and mic ───────────────────────────────────────────────────────

    fn endpoint(capture: bool) -> Option<IAudioEndpointVolume> {
        com();
        unsafe {
            let devices: IMMDeviceEnumerator = CoCreateInstance(&MMDeviceEnumerator, None, CLSCTX_ALL).ok()?;
            let device = devices
                .GetDefaultAudioEndpoint(if capture { eCapture } else { eRender }, eConsole)
                .ok()?;
            device.Activate::<IAudioEndpointVolume>(CLSCTX_ALL, None).ok()
        }
    }

    pub fn set_volume(percent: u8) -> Result<(), String> {
        let ep = endpoint(false).ok_or("No speakers found.")?;
        unsafe {
            ep.SetMasterVolumeLevelScalar(percent.min(100) as f32 / 100.0, std::ptr::null())
                .map_err(|e| e.message().to_string())?;
            if percent > 0 {
                let _ = ep.SetMute(false, std::ptr::null());
            }
        }
        Ok(())
    }

    pub fn set_mute(capture: bool, muted: bool) -> Result<(), String> {
        let ep = endpoint(capture).ok_or(if capture { "No microphone found." } else { "No speakers found." })?;
        unsafe { ep.SetMute(muted, std::ptr::null()) }.map_err(|e| e.message().to_string())
    }

    // ── Brightness (laptop screens, through WMI) ─────────────────────────────

    fn powershell(script: &str) -> Option<String> {
        let mut cmd = Command::new("powershell");
        cmd.args(["-NoProfile", "-NonInteractive", "-Command", script]);
        platform::no_console(&mut cmd);
        let out = cmd.output().ok()?;
        out.status.success().then(|| String::from_utf8_lossy(&out.stdout).trim().to_string())
    }

    pub fn brightness() -> Option<u8> {
        powershell("(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness -ErrorAction Stop | Select-Object -First 1).CurrentBrightness")?
            .parse()
            .ok()
    }

    pub fn set_brightness(percent: u8) -> Result<(), String> {
        let script = format!(
            "Invoke-CimMethod -InputObject (Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods -ErrorAction Stop | Select-Object -First 1) -MethodName WmiSetBrightness -Arguments @{{Timeout=0; Brightness={}}} | Out-Null",
            percent.min(100)
        );
        powershell(&script).map(|_| ()).ok_or_else(|| "This screen's brightness can't be changed from Windows.".into())
    }

    // ── Wi-Fi ────────────────────────────────────────────────────────────────

    fn wifi() -> (Option<String>, Option<u8>) {
        let mut cmd = Command::new("netsh");
        cmd.args(["wlan", "show", "interfaces"]);
        platform::no_console(&mut cmd);
        let Ok(out) = cmd.output() else { return (None, None) };
        let text = String::from_utf8_lossy(&out.stdout);
        let mut ssid = None;
        let mut signal = None;
        for line in text.lines() {
            let Some((k, v)) = line.split_once(':') else { continue };
            let k = k.trim();
            let v = v.trim();
            if k == "SSID" && !v.is_empty() {
                ssid = Some(v.to_string());
            } else if k == "Signal" {
                signal = v.trim_end_matches('%').trim().parse().ok();
            }
        }
        (ssid, signal)
    }

    pub fn controls(with_brightness: bool) -> Controls {
        let (volume, muted) = endpoint(false)
            .and_then(|ep| unsafe {
                let v = ep.GetMasterVolumeLevelScalar().ok()?;
                let m = ep.GetMute().ok()?.as_bool();
                Some((Some((v * 100.0).round() as u8), m))
            })
            .unwrap_or((None, false));
        let mic_muted = endpoint(true).and_then(|ep| unsafe { ep.GetMute().ok().map(|m| m.as_bool()) });
        let (wifi, wifi_signal) = wifi();
        Controls {
            volume,
            muted,
            mic_muted,
            brightness: if with_brightness { brightness() } else { None },
            wifi,
            wifi_signal,
        }
    }

    // ── Mic / camera in use ──────────────────────────────────────────────────

    /// Windows records, per app, when it last started and stopped using the
    /// mic or camera; "stopped" is 0 while it is still using it.
    fn in_use(capability: &str) -> bool {
        use winreg::enums::HKEY_CURRENT_USER;
        use winreg::RegKey;
        let base = format!(
            "Software\\Microsoft\\Windows\\CurrentVersion\\CapabilityAccessManager\\ConsentStore\\{capability}"
        );
        let Ok(root) = RegKey::predef(HKEY_CURRENT_USER).open_subkey(&base) else { return false };
        let busy = |key: &RegKey| -> bool {
            key.enum_keys().flatten().any(|name| {
                key.open_subkey(&name)
                    .ok()
                    .and_then(|k| k.get_value::<u64, _>("LastUsedTimeStop").ok())
                    .map(|stop| stop == 0)
                    .unwrap_or(false)
            })
        };
        if busy(&root) {
            return true;
        }
        root.open_subkey("NonPackaged").map(|np| busy(&np)).unwrap_or(false)
    }

    pub fn activity() -> Activity {
        Activity { mic_in_use: in_use("microphone"), camera_in_use: in_use("webcam"), downloads: downloads() }
    }

    // ── Shortcuts ────────────────────────────────────────────────────────────

    pub fn shortcut(which: &str) -> Result<(), String> {
        let open = |target: &str| -> Result<(), String> {
            let mut cmd = Command::new("cmd");
            cmd.args(["/C", "start", "", target]);
            platform::no_console(&mut cmd);
            cmd.spawn().map(|_| ()).map_err(|e| e.to_string())
        };
        match which {
            "lock" => unsafe { windows::Win32::System::Shutdown::LockWorkStation() }
                .map_err(|e| e.message().to_string()),
            "sleep" => {
                // SetSuspendState(hibernate = false, force = false, wakeup events allowed)
                let ok = unsafe { windows::Win32::System::Power::SetSuspendState(false, false, false) };
                if ok { Ok(()) } else { Err("Windows refused to sleep.".into()) }
            }
            "screenshot" => open("ms-screenclip:"),
            "downloads" => open(&platform::home_dir().join("Downloads").display().to_string()),
            "taskmgr" => open("taskmgr"),
            "settings" => open("ms-settings:"),
            other => Err(format!("Unknown shortcut {other}")),
        }
    }

    // ── Clipboard ────────────────────────────────────────────────────────────

    /// Changes every time anything is copied; cheap to ask.
    pub fn clipboard_seq() -> u32 {
        unsafe { windows::Win32::System::DataExchange::GetClipboardSequenceNumber() }
    }
}

#[cfg(not(windows))]
mod other {
    use super::*;

    pub fn now_playing() -> Option<NowPlaying> {
        None
    }
    pub fn media(_action: &str) -> Result<(), String> {
        Err("Media controls are a Windows feature.".into())
    }
    pub fn set_volume(_percent: u8) -> Result<(), String> {
        Err("Volume control is a Windows feature.".into())
    }
    pub fn set_mute(_capture: bool, _muted: bool) -> Result<(), String> {
        Err("Mute is a Windows feature.".into())
    }
    pub fn set_brightness(_percent: u8) -> Result<(), String> {
        Err("Brightness is a Windows feature.".into())
    }
    pub fn controls(_with_brightness: bool) -> Controls {
        Controls::default()
    }
    pub fn activity() -> Activity {
        Activity { downloads: downloads(), ..Activity::default() }
    }
    pub fn shortcut(_which: &str) -> Result<(), String> {
        Err("Shortcuts are a Windows feature.".into())
    }
    pub fn clipboard_seq() -> u32 {
        0
    }
    pub fn spotify_like() -> Result<(), String> {
        Err("Spotify likes are a Windows feature.".into())
    }
}

#[cfg(not(windows))]
pub use other::*;
