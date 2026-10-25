// Personal build: the Today panel — clock, weather now and for the next hours,
// and the next events from the calendar. Also the pieces the notch borrows.

import { h, clear } from "./dom";
import { State } from "../core/state";
import type { CalendarEvent } from "../core/bridge";
import type { ViewActions, ViewHost } from "./views";
import { clock, pct } from "./pc";
import { livePosition } from "./controls";

/** Lyrics in the notch while a song plays (Controls › ♪ turns them off). */
export function lyricsOn(): boolean {
  try {
    return localStorage.getItem("putshi.lyrics") !== "off";
  } catch {
    return true;
  }
}

/** The lyric line being sung now, if lyrics for this song are loaded. */
export function currentLyric(): string | null {
  const np = State.nowPlaying;
  const ly = State.lyrics;
  if (!np || !ly || !lyricsOn() || ly.key !== `${np.title}\u0001${np.artist}`) return null;
  const pos = livePosition() + 0.3;
  let line: string | null = null;
  for (const [t, text] of ly.lines) {
    if (t > pos) break;
    line = text;
  }
  return line || null;
}

/** WMO weather code → an emoji Windows draws in colour. */
export function weatherIcon(code: number, isDay = true): string {
  if (code === 0) return isDay ? "☀️" : "🌙";
  if (code <= 2) return isDay ? "🌤️" : "☁️";
  if (code === 3) return "☁️";
  if (code === 45 || code === 48) return "🌫️";
  if (code >= 51 && code <= 57) return "🌦️";
  if ((code >= 61 && code <= 67) || (code >= 80 && code <= 82)) return "🌧️";
  if ((code >= 71 && code <= 77) || code === 85 || code === 86) return "🌨️";
  if (code >= 95) return "⛈️";
  return "🌡️";
}

function hhmm(ms: number): string {
  return new Date(ms).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function sameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

/** "Now", "in 12 min", "14:00", "Tomorrow 09:00", "Wed 09:00". */
export function when(e: CalendarEvent, now = Date.now()): string {
  if (e.startMs <= now && e.endMs > now) return e.allDay ? "Today" : `Now, until ${hhmm(e.endMs)}`;
  const mins = Math.round((e.startMs - now) / 60000);
  if (!e.allDay && mins <= 60) return `In ${Math.max(1, mins)} min`;
  const d = new Date(e.startMs);
  const today = new Date(now);
  const tomorrow = new Date(now + 86400000);
  const day = sameDay(d, today)
    ? "Today"
    : sameDay(d, tomorrow)
      ? "Tomorrow"
      : d.toLocaleDateString([], { weekday: "short" });
  if (e.allDay) return day;
  return day === "Today" ? hhmm(e.startMs) : `${day} ${hhmm(e.startMs)}`;
}

/** The event to surface in the notch: one starting within 15 min or running now. */
export function liveEvent(now = Date.now()): CalendarEvent | null {
  return (
    State.events.find((e) => !e.allDay && e.startMs - now <= 15 * 60000 && e.endMs > now) ?? null
  );
}

export function buildToday(actions: ViewActions): ViewHost {
  const time = h("div", { class: "pc-time" });
  const date = h("div", { class: "pc-date" });
  const now = h("div", { class: "td-now" });
  const range = h("div", { class: "pc-host" });
  const timerRow = h("div", { class: "td-timer" });
  const hours = h("div", { class: "td-hours" });
  const events = h("div", { class: "td-events" });

  const body = h(
    "div",
    { class: "pc" },
    h("div", { class: "pc-clock" }, time, date, now, range, timerRow),
    h("div", { class: "td-right" }, hours, events),
  );

  let hoursKey = "";
  let timerKey = "";
  let eventsKey = "";

  return {
    el: h("div", { class: "view" }, h("div", { class: "card" }, body)),
    sync() {
      const d = new Date();
      time.textContent = clock(d);
      date.textContent = d.toLocaleDateString([], { weekday: "long", day: "numeric", month: "short" });

      const w = State.weather;
      if (w) {
        now.textContent = `${weatherIcon(w.code, w.isDay)} ${Math.round(w.temp)}°${w.city ? "  " + w.city : ""}`;
        range.textContent = `High ${Math.round(w.high)}°  Low ${Math.round(w.low)}°`;
      } else {
        now.textContent = State.weatherError ? "Weather unavailable" : "Checking the weather…";
        range.textContent = State.weatherError ?? "";
      }

      // Timer: quick picks, or the countdown with a stop button.
      const tk = State.timer ? `run:${timerLeft()}` : "idle";
      if (tk !== timerKey) {
        timerKey = tk;
        clear(timerRow);
        if (State.timer) {
          const stop = h("button", { class: "td-chip stop", text: "Stop" });
          stop.addEventListener("click", () => actions.stopTimer());
          timerRow.append(h("span", { class: "td-count", text: `⏱ ${timerLeft()}` }), stop);
        } else {
          timerRow.append(h("span", { class: "td-count dim", text: "⏱" }));
          for (const m of [5, 15, 25, 50]) {
            const b = h("button", { class: "td-chip", text: `${m}` });
            b.title = `${m}-minute timer`;
            b.addEventListener("click", () => actions.startTimer(m, m === 25 ? "Focus" : ""));
            timerRow.append(b);
          }
        }
      }

      const hk = w ? w.hours.map((x) => `${x.hour}:${x.temp}:${x.code}:${x.rain}`).join("|") : "";
      if (hk !== hoursKey) {
        hoursKey = hk;
        clear(hours);
        for (const x of w?.hours ?? []) {
          hours.append(
            h(
              "div",
              { class: "td-hour" },
              h("span", { class: "td-h", text: `${x.hour}h` }),
              h(
                "span",
                { class: "td-i" },
                weatherIcon(x.code, x.hour >= 7 && x.hour < 20),
                x.rain >= 30 ? h("span", { class: "td-r", text: `${x.rain}%` }) : null,
              ),
              h("span", { class: "td-t", text: `${Math.round(x.temp)}°` }),
            ),
          );
        }
      }

      const list = State.events.slice(0, 3);
      const ek = list.map((e) => `${e.title}|${when(e)}`).join("~") + (State.calendarError ?? "");
      if (ek !== eventsKey) {
        eventsKey = ek;
        clear(events);
        if (State.calendarError) {
          events.append(h("div", { class: "td-empty", text: State.calendarError }));
        } else if (list.length === 0) {
          const link = h("button", { class: "link-btn td-link", text: "Add your calendar in Settings" });
          link.addEventListener("click", () => actions.openSettingsWindow());
          events.append(h("div", { class: "td-empty" }, "Nothing coming up. ", link));
        } else {
          for (const e of list) {
            const soon = e.startMs - Date.now() <= 15 * 60000 && !e.allDay;
            events.append(
              h(
                "div",
                { class: soon ? "td-event soon" : "td-event" },
                h("span", { class: "td-when", text: when(e) }),
                h("span", { class: "td-title", text: e.title }),
              ),
            );
          }
        }
      }
    },
  };
}

/** The compact notch: "14:32 · ☀️ 24° · CPU 12% · ⚡82%", or the next event when it's close. */
export function timerLeft(): string {
  const t = State.timer;
  if (!t) return "";
  const s = Math.max(0, Math.ceil((t.endsAt - Date.now()) / 1000));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = String(s % 60).padStart(2, "0");
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${sec}` : `${m}:${sec}`;
}

function short(text: string, n: number): string {
  return text.length > n ? text.slice(0, n - 1) + "…" : text;
}

export function notchLine(): string {
  const parts = [clock()];
  if (State.alertText) {
    parts.push(`⚠️ ${State.alertText}`);
    return parts.join("  ·  ");
  }
  if (State.timer) {
    parts.push(`⏱ ${timerLeft()}${State.timer.label ? " " + short(State.timer.label, 18) : ""}`);
    return parts.join("  ·  ");
  }
  const dl = State.activity?.downloads[0];
  if (dl) {
    const mb = dl.bytes / 1024 ** 2;
    parts.push(`⬇ ${short(dl.name, 20)} ${mb >= 1024 ? (mb / 1024).toFixed(1) + " GB" : Math.round(mb) + " MB"}`);
    return parts.join("  ·  ");
  }
  const live = liveEvent();
  if (live) {
    parts.push(`${when(live)}: ${live.title.length > 22 ? live.title.slice(0, 21) + "…" : live.title}`);
    return parts.join("  ·  ");
  }
  const np = State.nowPlaying;
  if (np?.playing) {
    const lyric = currentLyric();
    if (lyric) {
      parts.push(`♪ ${short(lyric, 44)}`);
      return parts.join("  ·  ");
    }
    parts.push(`♫ ${short(np.title, 22)}${np.artist ? " — " + short(np.artist, 14) : ""}`);
    return parts.join("  ·  ");
  }
  const w = State.weather;
  if (w) parts.push(`${weatherIcon(w.code, w.isDay)} ${Math.round(w.temp)}°`);
  const s = State.stats;
  if (s) {
    parts.push(`CPU ${Math.round(s.cpu)}%`);
    if (s.battery != null) parts.push(`${s.charging ? "⚡" : ""}${s.battery}%`);
    else parts.push(`RAM ${pct(s.memUsed, s.memTotal)}%`);
  }
  return parts.join("  ·  ");
}
