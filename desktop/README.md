# Desktop (personal build of Coucou for Windows)

The Windows app is [Coucou](https://github.com/Louis-CFM/coucou) (MIT) built at
the commit pinned in `.github/workflows/coucou-windows.yml`, with the files in
`overlay/` copied over it before the build. Each overlay file is either new or a
full copy of Coucou's file with these changes:

| File | Change |
|---|---|
| `src-tauri/src/sysstats.rs` | New. CPU, memory, disk C:, network speed, battery, uptime, top apps. |
| `src-tauri/src/agent.rs` | New. Chat tools: folders, find/read files, PC status, open, write, PowerShell, memory. Open/write/run wait for Allow / Deny. |
| `src-tauri/src/claude.rs` | Chat is a tool loop (up to 16 rounds) with today's date and memory in the prompt. |
| `src-tauri/src/voice.rs` | New. Mic button presses Win+H (Windows voice typing). |
| `src/views/chat.ts`, `src/main.ts` | Progress line, mic / read-aloud / new-chat buttons, Mochi approval cards, Ctrl+Shift+Space. |
| `src-tauri/src/lib.rs` | New commands, global hotkey plugin; settings window re-centres when opened. |
| `src-tauri/Cargo.toml` | `sysinfo`, `winreg`, global-shortcut and clipboard plugins, more Windows API features. |
| `src-tauri/src/day.rs` | New. Weather (Open-Meteo, place from IP or a set city) and the next 7 days of a private iCal calendar link, with repeating events. Unit-tested. |
| `src-tauri/src/desk.rs` | New. Now playing + play/pause/skip (Windows media controls), volume and mic mute (Core Audio), brightness (WMI, laptops), Wi-Fi, mic/camera in use (registry), downloads in progress, lock/sleep/screenshot/folders. |
| `src-tauri/src/clip.rs` | New. Last 8 copied texts, memory only. |
| `src/views/controls.ts` | New. Controls and Clipboard panels. |
| `src-tauri/src/secrets.rs` | Two more stored values: `weather-city`, `calendar-ics-url`. |
| `src/settings/main.ts` | "Your day" section: city and calendar link. |
| `src/views/today.ts` | New. Today panel (clock, weather now and next 6 hours, next events) and the notch line. |
| `src/views/pc.ts`, `pc.css` | New. This PC panel: meters and top apps with a close button; styles for everything added. |
| `src/views/views.ts`, `icons.ts` | "This PC" tab (chip icon) in the header. |
| `src/island/island.ts` | Notch line and mic/camera dots; stats, media and activity every 2 s; weather/calendar every 5 min; timer; CPU, memory, disk and battery alerts. |
| `src/island/fsm.ts` | The notch never hides. |
| `src/core/state.ts` | Opens on Today; no integrations switched on by default. |
| `src/core/layout.ts`, `bridge.ts` | `pc` view size, wider notch, `systemStats()`. |

Notch priority: health alert › timer › download › event within 15 min › music playing › weather and stats.

When moving to a newer Coucou commit, re-copy those upstream files and re-apply
the changes above.

Push to `main` with a change under `desktop/` and GitHub builds the installer
into the **coucou-windows** release.
