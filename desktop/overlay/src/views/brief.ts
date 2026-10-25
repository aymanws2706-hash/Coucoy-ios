// Personal build: the morning briefing and the evening recap. The morning one
// opens the first time the PC is used after 5:00, the evening one the first
// time after 21:00; both can also be opened from the chat ("brief me").

import { h, clear } from "./dom";
import { Bridge, type UsageDay } from "../core/bridge";
import { State } from "../core/state";
import { weatherIcon, when } from "./today";
import type { ViewActions, ViewHost } from "./views";

function hours(secs: number): string {
  const m = Math.round(secs / 60);
  return m >= 60 ? `${Math.floor(m / 60)}h${String(m % 60).padStart(2, "0")}` : `${m} min`;
}

/** Friendly app names for the recap. */
function appName(exe: string): string {
  const known: Record<string, string> = {
    chrome: "Chrome", msedge: "Edge", firefox: "Firefox", Code: "VS Code", explorer: "File Explorer",
    WINWORD: "Word", EXCEL: "Excel", POWERPNT: "PowerPoint", OUTLOOK: "Outlook", Spotify: "Spotify",
    "ms-teams": "Teams", Teams: "Teams", WhatsApp: "WhatsApp", Discord: "Discord", Revit: "Revit",
    acad: "AutoCAD", SketchUp: "SketchUp", Photoshop: "Photoshop", Putshi: "Putshi",
  };
  return known[exe] ?? (exe.toLowerCase().includes("revit") ? "Revit" : exe);
}

export function buildBrief(actions: ViewActions): ViewHost {
  const title = h("div", { class: "title br-title" });
  const list = h("div", { class: "br-list" });
  const close = h("button", { class: "cv-chip", text: "Thanks", onclick: () => actions.collapse() });
  const el = h(
    "div",
    { class: "view" },
    h("div", { class: "card" }, h("div", { class: "br-wrap" }, title, list, h("div", { class: "br-foot" }, close))),
  );

  let usage: UsageDay | null = null;
  let whatsapp: { chat: string; text: string }[] | null = null;
  let loadedFor = "";
  let drawn = "";

  const line = (icon: string, text: string, dim = false) =>
    h("div", { class: dim ? "br-line dim" : "br-line" }, h("span", { class: "br-i", text: icon }), h("span", { text }));

  function draw() {
    clear(list);
    const evening = State.briefKind === "evening";
    const hr = new Date().getHours();
    title.textContent = evening ? "Your day" : hr < 12 ? "Good morning ☀️" : "Hello again";

    const now = Date.now();
    const endOfDay = new Date();
    endOfDay.setHours(23, 59, 59, 999);
    const tomorrow = new Date(endOfDay.getTime() + 1);
    const tomorrowEnd = new Date(endOfDay.getTime() + 86400000);

    if (!evening) {
      const w = State.weather;
      if (w) {
        const rain = w.hours.find((x) => x.rain >= 50);
        list.append(
          line(
            weatherIcon(w.code, w.isDay),
            `${Math.round(w.temp)}° now, up to ${Math.round(w.high)}°${rain ? ` · rain likely around ${rain.hour}h` : ""}`,
          ),
        );
      }
      const today = State.events.filter((e) => e.startMs <= endOfDay.getTime() && e.endMs > now);
      if (today.length) {
        for (const e of today.slice(0, 3)) list.append(line("📅", `${when(e)} — ${e.title}`));
        if (today.length > 3) list.append(line("📅", `and ${today.length - 3} more today`, true));
      } else {
        list.append(line("📅", "Nothing on the calendar today", true));
      }
      const due = State.remindersToday;
      if (due.length) list.append(line("⏰", due.slice(0, 2).join(" · ") + (due.length > 2 ? ` (+${due.length - 2})` : "")));
      if (whatsapp?.length) {
        const chats = [...new Set(whatsapp.map((m) => m.chat))];
        list.append(line("💬", `${whatsapp.length} WhatsApp message${whatsapp.length > 1 ? "s" : ""} from ${chats.slice(0, 3).join(", ")}${chats.length > 3 ? "…" : ""}`));
      }
    } else {
      const apps = Object.entries(usage?.apps ?? {}).sort((a, b) => b[1] - a[1]);
      const total = apps.reduce((n, [, s]) => n + s, 0);
      if (total > 0) {
        list.append(line("🖥️", `${hours(total)} at the PC (${usage?.first}–${usage?.last})`));
        list.append(line("📊", apps.slice(0, 3).map(([a, s]) => `${appName(a)} ${hours(s)}`).join(" · ")));
      } else {
        list.append(line("🖥️", "Not much PC time today", true));
      }
      const projects = Object.entries(usage?.revit ?? {}).sort((a, b) => b[1] - a[1]);
      if (projects.length) list.append(line("🏗️", projects.slice(0, 2).map(([p, s]) => `${p} ${hours(s)}`).join(" · ")));
      const open = State.remindersToday;
      if (open.length) list.append(line("⏰", `Still to do: ${open.slice(0, 2).join(" · ")}`));
      const next = State.events.find((e) => e.startMs >= tomorrow.getTime() && e.startMs < tomorrowEnd.getTime());
      list.append(next ? line("📅", `Tomorrow: ${next.allDay ? "all day" : new Date(next.startMs).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })} — ${next.title}`) : line("📅", "Nothing on the calendar tomorrow", true));
    }
  }

  return {
    el,
    sync() {
      if (State.view !== "brief") return;
      const key = `${State.briefKind}:${new Date().toDateString()}`;
      if (key !== loadedFor) {
        loadedFor = key;
        void Bridge.usageToday().then((u) => {
          usage = u;
          drawn = "";
          State.notify();
        });
        void Bridge.whatsappRecent().then((list) => {
          const since = Date.now() / 1000 - 12 * 3600;
          whatsapp = (list ?? []).filter((m) => m.at >= since);
          drawn = "";
          State.notify();
        });
      }
      const k = JSON.stringify([key, usage, whatsapp?.length, State.weather?.temp, State.events.length, State.remindersToday]);
      if (k === drawn) return;
      drawn = k;
      draw();
    },
  };
}
