// Personal build: dragging files in. Windows never lets a normal window
// (Explorer, the Desktop) drop files onto an app running as administrator, and
// apps started by an installer's "Launch" checkbox run as administrator. So
// Putshi restarts itself as the normal user when it finds itself elevated, and
// the drop zone also offers the regular file dialog.

#[cfg(windows)]
mod imp {
    use std::os::windows::process::CommandExt;
    use std::process::Command;
    use std::time::{Duration, SystemTime};

    use windows::Win32::Foundation::{CloseHandle, HANDLE};
    use windows::Win32::Security::{GetTokenInformation, TokenElevation, TOKEN_ELEVATION, TOKEN_QUERY};
    use windows::Win32::System::Threading::{GetCurrentProcess, OpenProcessToken};

    const CREATE_NO_WINDOW: u32 = 0x0800_0000;

    fn is_elevated() -> bool {
        unsafe {
            let mut token = HANDLE::default();
            if OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &mut token).is_err() {
                return false;
            }
            let mut info = TOKEN_ELEVATION::default();
            let mut len = 0u32;
            let ok = GetTokenInformation(
                token,
                TokenElevation,
                Some(&mut info as *mut _ as *mut _),
                std::mem::size_of::<TOKEN_ELEVATION>() as u32,
                &mut len,
            )
            .is_ok();
            let _ = CloseHandle(token);
            ok && info.TokenIsElevated != 0
        }
    }

    /// True when a normal-user copy was started and this one should quit.
    pub fn relaunch_unelevated() -> bool {
        if !is_elevated() {
            return false;
        }
        // Once per minute at most: if the restart comes back elevated too (UAC
        // off, or the built-in Administrator account), just keep running.
        let marker = std::env::temp_dir().join("putshi-unelevate.txt");
        let recent = std::fs::metadata(&marker)
            .and_then(|m| m.modified())
            .ok()
            .and_then(|t| SystemTime::now().duration_since(t).ok())
            .map(|age| age < Duration::from_secs(60))
            .unwrap_or(false);
        if recent {
            return false;
        }
        let Ok(exe) = std::env::current_exe() else { return false };
        let _ = std::fs::write(&marker, b"1");
        // Explorer hands the launch to the desktop's own (normal-user) Explorer.
        // The short wait lets this copy exit first, so the single-instance check
        // doesn't send the new one away.
        let spawned = Command::new("cmd.exe")
            .raw_arg(format!(
                "/d /c ping -n 3 127.0.0.1 >nul & explorer.exe \"{}\"",
                exe.display()
            ))
            .creation_flags(CREATE_NO_WINDOW)
            .spawn()
            .is_ok();
        spawned
    }

    pub fn pick_file() -> Option<String> {
        let script = "Add-Type -AssemblyName System.Windows.Forms; \
            [Console]::OutputEncoding = [Text.Encoding]::UTF8; \
            $owner = New-Object System.Windows.Forms.Form -Property @{ TopMost = $true }; \
            $d = New-Object System.Windows.Forms.OpenFileDialog; \
            $d.Title = 'Choose a file for Putshi'; \
            $d.InitialDirectory = [Environment]::GetFolderPath('MyDocuments'); \
            if ($d.ShowDialog($owner) -eq 'OK') { $d.FileName }";
        let out = Command::new("powershell.exe")
            .args(["-NoProfile", "-NonInteractive", "-STA", "-Command", script])
            .creation_flags(CREATE_NO_WINDOW)
            .output()
            .ok()?;
        let path = String::from_utf8_lossy(&out.stdout).trim().to_string();
        (!path.is_empty()).then_some(path)
    }
}

#[cfg(not(windows))]
mod imp {
    pub fn relaunch_unelevated() -> bool {
        false
    }

    pub fn pick_file() -> Option<String> {
        let out = std::process::Command::new("zenity").arg("--file-selection").output().ok()?;
        let path = String::from_utf8_lossy(&out.stdout).trim().to_string();
        (!path.is_empty()).then_some(path)
    }
}

pub use imp::{pick_file, relaunch_unelevated};
