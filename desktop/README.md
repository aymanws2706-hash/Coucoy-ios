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
| `src-tauri/src/phone.rs` | New. Phone link: web app + JSON API on 127.0.0.1:8771, token auth, shared over HTTPS by `tailscale serve`, pairing QR. |
| `src-tauri/src/glass.rs`, `src/glass.css` | New. Liquid Glass: acrylic blur behind the island, window cut to the island's shape; translucent layers. Toggle in Settings › General. |
| `src/mochi/glass.ts`, `engine.ts`, `greeting.ts`, `src/upload/canvas.ts` | The character is a liquid-glass droplet (rippling outline, mood colour pooling inside), drawn the same everywhere. |
| `src-tauri/icons/*` | Droplet icons: app/installer tile, an opaque droplet for tray sizes, and `putshi-512.png` for the phone. |
| `src-tauri/tauri.conf.json`, `tray.rs`, `index.html`, `settings.html`, `scripts/pack.mjs` | Named Putshi (data folders and keys keep Coucou's names, so nothing is lost). |
| `src-tauri/src/jobs.rs` | New. Tasks for the PC: from the phone (signed with the pairing token, via the phone link or the private ntfy topic "<topic>-jobs") or scheduled by the assistant; run when due, results pushed to the phone. |
| `public/sw.js`, `src/phone/offline.ts` | Phone offline mode: the page is kept on the phone; with the PC off it chats with Claude directly, queues tasks for the PC, and sets reminders through ntfy. |
| Reminders | `remind_me` on PC and phone: notch at the time plus a scheduled ntfy alert (works with the PC off, up to 3 days ahead). |
| `src-tauri/src/awareness.rs` | New. Awareness (opt-in, three levels: window titles, messaging-app windows, whole screen every 15 min): pictures go to Claude Haiku to spot commitments and are never saved; ignore list and private windows skipped; Pause stops it. Suggestions open a "Putshi noticed" card with Remind me / In 1 hour / Not now. |
| `src-tauri/src/convert.rs`, `src/views/convert.ts`, `src/views/upload.ts`, `src/upload/canvas.ts` | New. Convert: drop a file › Convert… › pick a format from glass bubbles that burst out of the droplet. Pictures with the `image` crate (HEIC/HEIF through Windows WIC, image → PDF written directly), Office documents through Office COM (LibreOffice fallback), audio/video through ffmpeg (installable from the card with winget). Saved next to the original, never overwriting. Also a `convert_file` chat tool. Unit-tested. |
| `src-tauri/src/whatsapp.rs` | New. WhatsApp without logging in: with Settings › Awareness › WhatsApp messages on, new WhatsApp notifications are read from Windows' notification database (`rusqlite`, from a temporary copy) every 30 s and checked for things to follow up; the chat can list them (`whatsapp_messages`) and write a message (`whatsapp_send`), which opens WhatsApp with the text typed for the user to send. Unit-tested. |
| `src-tauri/src/elevation.rs` | New. Dropping files in: started as administrator (an installer's Launch checkbox), Windows blocks drags from Explorer, so Putshi restarts itself as the normal user through Explorer (at most once a minute). The drop zone also gets an "or choose a file…" button with the Windows file dialog. |
| `src-tauri/src/push.rs` | New. ntfy alerts to the phone, only when the PC has been idle 2 min. |
| `phone.html`, `src/phone/`, `vite.config.ts` | New. Putshi phone page (chat, approvals, music, timer, today, PC, lock/sleep), built with the rest. |
| `src/island/hooks.ts` | Claude Code permission / finished also alert the phone. |
| `src-tauri/src/secrets.rs` | More stored values: `weather-city`, `calendar-ics-url`, `phone-token`, `ntfy-topic`. |
| `src/settings/main.ts` | "Your day" (city, calendar link) and "Phone" (turn on, QR code, ntfy topic) sections. |
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
