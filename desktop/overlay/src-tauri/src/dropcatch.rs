// Personal build: a second way for dropped files to reach Putshi on Windows.
//
// The island is a WebView2 window, and WebView2 and Tauri both register OLE
// drop targets on it; on some PCs the webview's own target wins and refuses
// every file. This sidesteps OLE completely: while something is being dragged
// over the island (the button went down outside it and is still held), an
// invisible window takes the island's place and accepts files the classic way
// (WS_EX_ACCEPTFILES / WM_DROPFILES). It hides again as soon as the button is
// released, so it never gets in the way of clicks.

use serde_json::json;
use tauri::{AppHandle, Emitter};

#[cfg(windows)]
mod imp {
    use std::sync::atomic::{AtomicIsize, Ordering};
    use std::sync::OnceLock;
    use std::time::{Duration, Instant};

    use tauri::AppHandle;
    use windows::core::w;
    use windows::Win32::Foundation::{COLORREF, HWND, LPARAM, LRESULT, POINT, WPARAM};
    use windows::Win32::Graphics::Gdi::{GetStockObject, HBRUSH, BLACK_BRUSH};
    use windows::Win32::System::LibraryLoader::GetModuleHandleW;
    use windows::Win32::UI::Input::KeyboardAndMouse::{GetAsyncKeyState, VK_LBUTTON};
    use windows::Win32::UI::Shell::{DragAcceptFiles, DragFinish, DragQueryFileW, HDROP};
    use windows::Win32::UI::WindowsAndMessaging::{
        ChangeWindowMessageFilterEx, CreateWindowExW, DefWindowProcW, GetCursorPos, RegisterClassW,
        SetLayeredWindowAttributes, SetWindowPos, HWND_TOPMOST, LWA_ALPHA, MA_NOACTIVATE, MSGFLT_ALLOW,
        SWP_ASYNCWINDOWPOS, SWP_HIDEWINDOW, SWP_NOACTIVATE, SWP_NOMOVE, SWP_NOSIZE, SWP_NOZORDER, SWP_SHOWWINDOW,
        WM_COPYDATA, WM_DROPFILES, WM_MOUSEACTIVATE, WNDCLASSW, WS_EX_ACCEPTFILES, WS_EX_LAYERED, WS_EX_NOACTIVATE,
        WS_EX_TOOLWINDOW, WS_EX_TOPMOST, WS_POPUP,
    };

    static HWND_RAW: AtomicIsize = AtomicIsize::new(0);
    static APP: OnceLock<AppHandle> = OnceLock::new();
    const WM_COPYGLOBALDATA: u32 = 0x0049;

    fn hwnd() -> Option<HWND> {
        let raw = HWND_RAW.load(Ordering::Relaxed);
        (raw != 0).then(|| HWND(raw as *mut _))
    }

    unsafe extern "system" fn wndproc(hwnd: HWND, msg: u32, wp: WPARAM, lp: LPARAM) -> LRESULT {
        match msg {
            WM_DROPFILES => {
                let hdrop = HDROP(wp.0 as *mut _);
                let mut paths = Vec::new();
                let count = unsafe { DragQueryFileW(hdrop, u32::MAX, None) };
                for i in 0..count {
                    let len = unsafe { DragQueryFileW(hdrop, i, None) } as usize;
                    let mut buf = vec![0u16; len + 1];
                    let got = unsafe { DragQueryFileW(hdrop, i, Some(&mut buf)) } as usize;
                    paths.push(String::from_utf16_lossy(&buf[..got]));
                }
                unsafe { DragFinish(hdrop) };
                hide();
                if let Some(app) = APP.get() {
                    crate::log::line(format!("drop catcher: {} file(s)", paths.len()));
                    super::emit(app, "drop", paths);
                }
                LRESULT(0)
            }
            WM_MOUSEACTIVATE => LRESULT(MA_NOACTIVATE as isize),
            _ => unsafe { DefWindowProcW(hwnd, msg, wp, lp) },
        }
    }

    /// Creates the (hidden) catcher. Must run on the main thread, whose event
    /// loop pumps its messages.
    pub fn create(app: &AppHandle) {
        let _ = APP.set(app.clone());
        unsafe {
            let Ok(module) = GetModuleHandleW(None) else { return };
            let class = WNDCLASSW {
                lpfnWndProc: Some(wndproc),
                hInstance: module.into(),
                lpszClassName: w!("PutshiDropCatcher"),
                hbrBackground: HBRUSH(GetStockObject(BLACK_BRUSH).0),
                ..Default::default()
            };
            RegisterClassW(&class);
            let Ok(h) = CreateWindowExW(
                WS_EX_ACCEPTFILES | WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_TOPMOST | WS_EX_NOACTIVATE,
                w!("PutshiDropCatcher"),
                w!("Putshi drop"),
                WS_POPUP,
                0,
                0,
                1,
                1,
                None,
                None,
                Some(module.into()),
                None,
            ) else {
                crate::log::line("drop catcher: could not create its window");
                return;
            };
            // Alpha 1 of 255: invisible, but still hit by the mouse (0 isn't).
            let _ = SetLayeredWindowAttributes(h, COLORREF(0), 1, LWA_ALPHA);
            DragAcceptFiles(h, true);
            // Lets a drop through even across privilege levels.
            for m in [WM_DROPFILES, WM_COPYDATA, WM_COPYGLOBALDATA] {
                let _ = ChangeWindowMessageFilterEx(h, m, MSGFLT_ALLOW, None);
            }
            HWND_RAW.store(h.0 as isize, Ordering::Relaxed);
        }
    }

    fn show(x: i32, y: i32, w: i32, h: i32) {
        let Some(hw) = hwnd() else { return };
        unsafe {
            let _ = SetWindowPos(hw, Some(HWND_TOPMOST), x, y, w, h, SWP_NOACTIVATE | SWP_SHOWWINDOW | SWP_ASYNCWINDOWPOS);
        }
    }

    pub fn hide() {
        let Some(hw) = hwnd() else { return };
        unsafe {
            let _ = SetWindowPos(
                hw,
                None,
                0,
                0,
                0,
                0,
                SWP_NOACTIVATE | SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_HIDEWINDOW | SWP_ASYNCWINDOWPOS,
            );
        }
    }

    /// Watches the mouse: a press that started elsewhere and is held over the
    /// island is a drag coming in.
    pub fn watch(app: AppHandle) {
        std::thread::spawn(move || {
            let mut was_down = false;
            let mut started_inside = false;
            let mut shown = false;
            let mut released_at: Option<Instant> = None;
            let mut over_since: Option<Instant> = None;
            let mut announced = false;
            loop {
                std::thread::sleep(Duration::from_millis(25));
                let down = unsafe { (GetAsyncKeyState(VK_LBUTTON.0 as i32) as u16 & 0x8000) != 0 };
                let mut p = POINT::default();
                if unsafe { GetCursorPos(&mut p) }.is_err() {
                    continue;
                }
                let Some(win) = crate::island::window(&app) else { continue };
                let (Ok(pos), Ok(size)) = (win.outer_position(), win.outer_size()) else { continue };
                let (x, y, w, h) = (pos.x, pos.y, size.width as i32, size.height as i32);
                let inside = p.x >= x && p.x < x + w && p.y >= y && p.y < y + h;

                if down && !was_down {
                    started_inside = inside;
                }
                was_down = down;

                if down && !started_inside && inside {
                    released_at = None;
                    if !shown {
                        shown = true;
                        show(x, y, w, h);
                    }
                    // Opened only after a short hover, so a window dragged to
                    // the top of the screen doesn't open the drop zone.
                    let since = *over_since.get_or_insert_with(Instant::now);
                    if !announced && since.elapsed() > Duration::from_millis(300) {
                        announced = true;
                        super::emit(&app, "enter", Vec::new());
                    }
                } else if shown {
                    over_since = None;
                    if down {
                        // Dragged back out.
                        shown = false;
                        hide();
                        if std::mem::take(&mut announced) {
                            super::emit(&app, "leave", Vec::new());
                        }
                    } else {
                        // Released: give the drop message a moment to arrive.
                        let t = *released_at.get_or_insert_with(Instant::now);
                        if t.elapsed() > Duration::from_millis(600) {
                            shown = false;
                            released_at = None;
                            hide();
                            if std::mem::take(&mut announced) {
                                super::emit(&app, "leave", Vec::new());
                            }
                        }
                    }
                }
            }
        });
    }
}

fn emit(app: &AppHandle, kind: &str, paths: Vec<String>) {
    let _ = app.emit("drop-catcher", json!({ "type": kind, "paths": paths }));
}

pub fn start(app: &AppHandle) {
    #[cfg(windows)]
    {
        let handle = app.clone();
        let _ = app.run_on_main_thread(move || imp::create(&handle));
        imp::watch(app.clone());
    }
    #[cfg(not(windows))]
    let _ = app;
}
