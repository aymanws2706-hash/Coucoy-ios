# Putshi for iPhone

Putshi, a little assistant built on Mochi, the mascot from [Coucou](https://github.com/Louis-CFM/coucou), as a
real iPhone app:

- **The app**: Mochi animated full screen with the real Coucou engine. All 11
  states, 8 expressions, every outfit, the original sounds. Tap to poke (three
  times for dizzy), hold for hearts, drag and its eyes follow your finger.
- **Dynamic Island and lock screen**: turn on "Putshi in the Dynamic Island" and
  Mochi stays there while you use other apps.
- **Home screen and lock screen widget**: Mochi in the seasonal outfit, asleep
  from 23:00 to 07:00.
- **Shortcuts**: links like `putshi://state/thinking` change Mochi from the
  Shortcuts app or from JARVIS.

## Putshi the assistant

- **Chat tab**: talk to Putshi. It thinks with Claude (`claude-opus-5-5`),
  replies in your language, and pushes back with options when a plan is shaky.
- **Tasks**: for multi-step jobs Putshi makes a task with steps. You follow it
  live in the **Tasks** tab, on the **lock screen** and in the **Dynamic Island**.
- **Your PC**: anything that needs the computer goes to the Putshi bridge on
  your PC (`bridge/`). Writing files, running commands and opening apps wait
  for your **Allow / Deny** on the phone.
- **Settings**: your Anthropic API key (kept in the Keychain), your PC's address
  and bridge token.
- **Memory**: tell Putshi something lasting ("remember I use Revit 2025") and it
  keeps it for every future chat. See and delete it in **Settings › Memory**.
- **Tasks widget**: add **Putshi tasks** to your home screen (small, medium or
  large) to see the current task and its steps. It needs the App Group, which
  AltStore sets up; if your install can't share data, the widget says so.
- **Shortcuts / Siri**: `putshi://ask?q=your request` sends a message.

PC setup: see [bridge/README.md](bridge/README.md).

No Mac and no paid Apple account needed. GitHub builds it, you install it from
Windows with your free Apple ID.

## 1. Get the app file

Every push to `main` builds the app on GitHub's free Mac servers (about 5
minutes). When the **Actions** tab shows a green tick, open **Releases ›
latest** and download `Putshi.ipa`.

## 2. Install it from Windows (free Apple ID)

Pick one.

**AltStore (recommended, refreshes itself)**
1. Install iTunes and iCloud *from apple.com* (not the Microsoft Store versions).
2. Install AltServer from <https://altstore.io> and sign in with your Apple ID.
3. Plug in the iPhone, click the AltServer tray icon › Install AltStore › your iPhone.
4. On the iPhone: Settings › General › VPN & Device Management › trust your Apple ID.
   Turn on Settings › Privacy & Security › Developer Mode and restart when asked.
5. Copy `Putshi.ipa` to the phone (Files app), open AltStore › My Apps › **+** › pick it.
6. In iTunes, tick "Sync with this iPhone over Wi-Fi". From now on AltServer
   re-signs Putshi automatically whenever the PC and phone are on the same Wi-Fi,
   so the 7-day expiry never bites.

**Sideloadly (simplest, manual every 7 days)**
1. Install iTunes and iCloud from apple.com, then Sideloadly from <https://sideloadly.io>.
2. Plug in the iPhone, drop `Putshi.ipa` on Sideloadly, enter your Apple ID, Start.
3. Trust your Apple ID and turn on Developer Mode as in steps 4 above.
4. Repeat step 2 once a week.

## 3. Use it

- Open Putshi, turn on **Putshi in the Dynamic Island**.
- Long-press the home screen › **+** › Putshi to add the widget. On the lock
  screen: long-press › Customize › Lock Screen › add widget › Putshi.

## Limits of the free route

| | Free Apple ID | Paid (99 USD/year) |
|---|---|---|
| App keeps working | 7 days, AltStore refreshes it | 1 year |
| Dynamic Island updated by JARVIS while the app is closed | No (needs push) | Yes, with a push server |
| Sideloaded apps at once | 3 | No limit |

iOS removes any Live Activity after about 8 hours; opening Putshi puts it
back.

## Shortcuts / JARVIS links

| Link | Effect |
|---|---|
| `putshi://state/thinking` | any state: idle, working, thinking, searching, approval, question, error, finished, ratelimit, sleeping, dizzy |
| `putshi://emote/love` | love, surprised, proud, wink, yawn, happy, annoyed |
| `putshi://outfit/witchHat` | auto, none, partyHat, beanie, crown, sunglasses, roundGlasses, bow, scarf, witchHat, pumpkin, santaHat, bunnyEars |
| `putshi://island/on` · `putshi://island/off` | Dynamic Island on or off |
| `putshi://ask?q=...` | sends a message to Putshi |

## How it's built

- `Sources/CoucouKit/` is Coucou's own shared engine, copied unchanged from
  commit `f4bfb49` (MIT, see `LICENSE-COUCOU-MIT`).
- `Sources/App`, `Sources/Widget`, `Sources/Shared` are this app.
- The sounds and the app icon are downloaded from the Coucou repo at build time and are not
  stored here. Mochi's name, look and sounds are © Louis Raillé
  (`LICENSE-ASSETS-COUCOU.md`); this build is for personal use.
- `project.yml` is an [XcodeGen](https://github.com/yonaskolb/XcodeGen) spec;
  `.github/workflows/build.yml` builds the unsigned `.ipa`.
