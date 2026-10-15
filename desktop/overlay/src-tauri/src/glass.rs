// Personal build: Liquid Glass. Windows blurs whatever is behind the island
// (acrylic), and the window is cut to the island's own rounded shape so only
// the island is glass, not the whole 720×320 window around it. The shape is
// updated as the island animates, from the same rect the click-through uses.

use std::sync::atomic::{AtomicBool, Ordering};

use tauri::WebviewWindow;

static ON: AtomicBool = AtomicBool::new(false);

/// Turns the blur on or off; the page keeps the user's choice. Turning it off
/// when it was never on does nothing at all: on Windows 11 even "clearing" the
/// backdrop changes how the window is painted (a solid grey box).
pub fn set_enabled(win: &WebviewWindow, on: bool) -> bool {
    let was = ON.load(Ordering::Relaxed);
    if !on {
        if was {
            imp::restore_default(win);
            imp::clear_region(win);
            ON.store(false, Ordering::Relaxed);
        }
        return true;
    }
    let applied = imp::apply(win);
    ON.store(applied, Ordering::Relaxed);
    if !applied {
        imp::clear_region(win);
    }
    applied
}

/// The island's rect in logical window pixels and its bottom corner radius.
pub fn shape(win: &WebviewWindow, x: f64, y: f64, w: f64, h: f64, radius: f64) {
    if ON.load(Ordering::Relaxed) {
        let scale = win.scale_factor().unwrap_or(1.0);
        imp::set_region(win, x * scale, y * scale, w * scale, h * scale, radius * scale);
    }
}

#[cfg(windows)]
mod imp {
    use tauri::WebviewWindow;
    use windows::Win32::Foundation::HWND;
    use windows::Win32::Graphics::Gdi::{CreateRoundRectRgn, CreateRectRgn, SetWindowRgn, HRGN};

    fn hwnd(win: &WebviewWindow) -> Option<HWND> {
        win.hwnd().ok().map(|h| HWND(h.0 as _))
    }

    pub fn apply(win: &WebviewWindow) -> bool {
        // A dark, light tint: the colour comes from the page's own layers.
        window_vibrancy::apply_acrylic(win, Some((14, 16, 22, 60))).is_ok()
    }

    /// Back to exactly how the window was before: backdrop "auto" (0), which
    /// is the default — not "none" (1), which Windows 11 paints solid.
    pub fn restore_default(win: &WebviewWindow) {
        use windows::Win32::Graphics::Dwm::{DwmSetWindowAttribute, DWMWA_SYSTEMBACKDROP_TYPE};
        // Windows 10 turns the accent off here; on Windows 11 this sets the
        // backdrop to "none", which the next call puts back to "auto".
        let _ = window_vibrancy::clear_acrylic(win);
        let Some(hwnd) = hwnd(win) else { return };
        let auto: u32 = 0;
        unsafe {
            let _ = DwmSetWindowAttribute(
                hwnd,
                DWMWA_SYSTEMBACKDROP_TYPE,
                &auto as *const u32 as _,
                std::mem::size_of::<u32>() as u32,
            );
        }
    }

    pub fn set_region(win: &WebviewWindow, x: f64, y: f64, w: f64, h: f64, r: f64) {
        let Some(hwnd) = hwnd(win) else { return };
        unsafe {
            let rgn = if h < 1.0 {
                // Hidden: keep the thin wake strip at the top centre reachable.
                let size = win.inner_size().map(|s| s.width as i32).unwrap_or(720);
                let half = (120.0 * win.scale_factor().unwrap_or(1.0)) as i32;
                CreateRectRgn(size / 2 - half, 0, size / 2 + half, 8)
            } else {
                // Rounded on all four corners, then pushed up by the radius so
                // the top edge (against the screen edge) stays square.
                let d = (2.0 * r).round() as i32;
                CreateRoundRectRgn(
                    x.round() as i32,
                    (y - r).round() as i32,
                    (x + w).round() as i32 + 1,
                    (y + h).round() as i32 + 1,
                    d,
                    d,
                )
            };
            // The system owns the region after this call.
            let _ = SetWindowRgn(hwnd, Some(rgn), true);
        }
    }

    pub fn clear_region(win: &WebviewWindow) {
        if let Some(hwnd) = hwnd(win) {
            unsafe {
                let _ = SetWindowRgn(hwnd, Some(HRGN::default()), true);
            }
        }
    }
}

#[cfg(not(windows))]
mod imp {
    use tauri::WebviewWindow;

    pub fn apply(_win: &WebviewWindow) -> bool {
        false
    }
    pub fn restore_default(_win: &WebviewWindow) {}
    pub fn set_region(_win: &WebviewWindow, _x: f64, _y: f64, _w: f64, _h: f64, _r: f64) {}
    pub fn clear_region(_win: &WebviewWindow) {}
}
