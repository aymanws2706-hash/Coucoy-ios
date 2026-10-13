// Personal build: talking to Mochi. Windows already has voice typing (Win+H),
// which types what you say into whatever has focus; the chat field takes focus
// first, then this presses Win+H for you. Replies are read aloud by the page
// with the voices Windows ships.

#[cfg(windows)]
pub fn start_dictation() -> Result<(), String> {
    use windows::Win32::UI::Input::KeyboardAndMouse::{
        SendInput, INPUT, INPUT_0, INPUT_KEYBOARD, KEYBDINPUT, KEYBD_EVENT_FLAGS, KEYEVENTF_KEYUP,
        VIRTUAL_KEY, VK_LWIN,
    };

    fn key(vk: VIRTUAL_KEY, up: bool) -> INPUT {
        INPUT {
            r#type: INPUT_KEYBOARD,
            Anonymous: INPUT_0 {
                ki: KEYBDINPUT {
                    wVk: vk,
                    wScan: 0,
                    dwFlags: if up { KEYEVENTF_KEYUP } else { KEYBD_EVENT_FLAGS(0) },
                    time: 0,
                    dwExtraInfo: 0,
                },
            },
        }
    }

    let h = VIRTUAL_KEY(0x48);
    let inputs = [key(VK_LWIN, false), key(h, false), key(h, true), key(VK_LWIN, true)];
    let sent = unsafe { SendInput(&inputs, std::mem::size_of::<INPUT>() as i32) };
    if sent as usize == inputs.len() {
        Ok(())
    } else {
        Err("Windows didn't accept the Win+H key press.".into())
    }
}

#[cfg(not(windows))]
pub fn start_dictation() -> Result<(), String> {
    Err("Voice typing is a Windows feature.".into())
}
