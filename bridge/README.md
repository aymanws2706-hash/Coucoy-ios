# Putshi bridge (runs on your PC)

Putshi on the iPhone sends jobs here. The bridge does them with Claude on your
PC, reports each step back to the phone (Tasks tab, lock screen, Dynamic
Island) and asks you on the phone before it writes files, runs commands or
opens apps.

## Setup on Windows (once)

1. Copy this `bridge` folder to your PC, for example next to JARVIS:
   `C:\Users\ayman\jarvis\putshi_bridge\`.
2. In PowerShell in that folder:
   ```powershell
   pip install -r requirements.txt
   python putshi_bridge.py --env C:\Users\ayman\jarvis\.env
   ```
   It prints a **token**. `--env` reuses the Anthropic key from JARVIS's `.env`.
3. Make it reachable from the phone over HTTPS with Tailscale (installed on
   both the PC and the iPhone, signed in to the same account):
   ```powershell
   tailscale serve --bg 8770
   ```
   It prints an address like `https://your-pc.tail1234.ts.net`.
4. In Putshi on the iPhone, open **Settings › Your PC**, paste the address and
   the token, and tap **Test connection**.

## What Putshi can do on the PC

| Tool | Asks you first? |
|---|---|
| List a folder, find files, read a text file | No |
| Write a text file | Yes |
| Open a file, folder or app | Yes |
| Run a PowerShell command | Yes, and shows the exact command |

## Connecting it to JARVIS

The bridge has its own small Claude agent so it works on its own. To make
JARVIS do the work instead (memory, voice, Revit tools), replace `run_agent()`
in `putshi_bridge.py` with a call into JARVIS's brain, keeping the
`task.step()`, `task.ask()` and `task.finish()` calls so the phone still sees
progress and approvals.
