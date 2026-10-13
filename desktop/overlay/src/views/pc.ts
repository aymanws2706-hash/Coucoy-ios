// Personal build: the desktop panel the island opens on, and the clock and
// stats line shown in the compact notch.

import "./pc.css";
import { h, clear } from "./dom";
import { State } from "../core/state";
import { Bridge, type AppUsage, type SystemStats } from "../core/bridge";
import type { ViewActions, ViewHost } from "./views";

const GB = 1024 ** 3;

export function pct(used: number, total: number): number {
  return total > 0 ? Math.round((used / total) * 100) : 0;
}

function gb(bytes: number): string {
  const v = bytes / GB;
  return v >= 100 ? v.toFixed(0) : v.toFixed(1);
}

export function rate(bytesPerSec: number): string {
  if (bytesPerSec >= 1024 ** 2) return `${(bytesPerSec / 1024 ** 2).toFixed(1)} MB/s`;
  if (bytesPerSec >= 1024) return `${Math.round(bytesPerSec / 1024)} KB/s`;
  return `${Math.round(bytesPerSec)} B/s`;
}

function uptime(secs: number): string {
  const d = Math.floor(secs / 86400);
  const hrs = Math.floor((secs % 86400) / 3600);
  const m = Math.floor((secs % 3600) / 60);
  if (d > 0) return `${d}d ${hrs}h`;
  if (hrs > 0) return `${hrs}h ${m}m`;
  return `${m}m`;
}

export function clock(now = new Date()): string {
  return now.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

/** Green → amber → red as a meter fills up. */
function level(p: number): string {
  if (p >= 90) return "var(--red)";
  if (p >= 70) return "var(--amber)";
  return "var(--green-2)";
}

interface Meter {
  el: HTMLElement;
  set(label: string, value: string, fill: number, color?: string): void;
}

function meter(): Meter {
  const label = h("span", { class: "m-label" });
  const value = h("span", { class: "m-value" });
  const bar = h("i");
  const el = h(
    "div",
    { class: "meter" },
    h("div", { class: "m-head" }, label, value),
    h("div", { class: "m-bar" }, bar),
  );
  return {
    el,
    set(l, v, fill, color) {
      label.textContent = l;
      value.textContent = v;
      const f = Math.max(0, Math.min(100, fill));
      bar.style.width = `${f}%`;
      bar.style.background = color ?? level(f);
    },
  };
}

function appRow(app: AppUsage, actions: ViewActions): HTMLElement {
  const name = h("span", { class: "ap-name", text: app.name });
  name.title = `${app.processes} process${app.processes === 1 ? "" : "es"}`;
  const cpu = h("span", { class: "ap-cpu", text: `${app.cpu.toFixed(app.cpu < 10 ? 1 : 0)}%` });
  cpu.style.color = app.cpu >= 50 ? "var(--red)" : app.cpu >= 20 ? "var(--amber)" : "";
  const mem = h("span", { class: "ap-mem", text: app.memory >= GB ? `${gb(app.memory)} GB` : `${Math.round(app.memory / 1024 ** 2)} MB` });
  const kill = h("button", { class: "ap-kill", title: `Close ${app.name}`, text: "✕" });
  const row = h("div", { class: "ap-row" }, name, cpu, mem, kill);

  // Ask right in the row: closing an app can lose unsaved work.
  kill.addEventListener("click", () => {
    actions.blip();
    clear(row);
    const yes = h("button", { class: "ap-yes", text: "Close" });
    const no = h("button", { class: "ap-no", text: "Keep" });
    row.classList.add("confirm");
    const ask = h("span", { class: "ap-ask", text: `Close ${app.name}?` });
    ask.title = "Anything unsaved in it is lost.";
    row.append(ask, no, yes);
    no.addEventListener("click", () => {
      row.classList.remove("confirm");
      clear(row);
      row.append(name, cpu, mem, kill);
    });
    yes.addEventListener("click", async () => {
      clear(row);
      row.append(h("span", { class: "ap-ask", text: `Closing ${app.name}…` }));
      const n = (await Bridge.killApp(app.name)) ?? 0;
      clear(row);
      row.append(h("span", { class: "ap-ask", text: n > 0 ? `Closed ${app.name}.` : `Windows didn't let me close ${app.name}.` }));
      State.topApps = State.topApps.filter((a) => a.name !== app.name || n === 0);
    });
  });
  return row;
}

export function buildPc(actions: ViewActions): ViewHost {
  const cpu = meter();
  const mem = meter();
  const disk = meter();
  const fourth = meter();
  const info = h("div", { class: "ap-info" });
  const apps = h("div", { class: "ap-list" });

  const body = h(
    "div",
    { class: "pc" },
    h("div", { class: "pc-meters" }, cpu.el, mem.el, disk.el, fourth.el),
    h("div", { class: "ap" }, h("div", { class: "ap-head" }, h("span", { text: "Top apps" }), info), apps),
  );
  const card = h("div", { class: "card" }, body);

  let appsKey: string | null = null;

  return {
    el: h("div", { class: "view" }, card),
    sync() {
      const s: SystemStats | null = State.stats;
      if (!s) {
        info.textContent = "Reading your PC…";
        cpu.set("CPU", "–", 0);
        mem.set("Memory", "–", 0);
        disk.set("Disk C:", "–", 0);
        fourth.set("Battery", "–", 0);
        return;
      }
      info.textContent = `↓ ${rate(s.netDown)}  ↑ ${rate(s.netUp)}  ·  on ${uptime(s.uptimeSecs)}`;
      info.title = s.host;

      const c = Math.round(s.cpu);
      cpu.set("CPU", `${c}%`, c);
      const m = pct(s.memUsed, s.memTotal);
      mem.set("Memory", `${m}%`, m);
      mem.el.title = `${gb(s.memUsed)} of ${gb(s.memTotal)} GB in use`;
      const d = pct(s.diskUsed, s.diskTotal);
      disk.set("Free on C:", `${Math.round((s.diskTotal - s.diskUsed) / GB)} GB`, d);
      disk.el.title = `${gb(s.diskUsed)} of ${gb(s.diskTotal)} GB used`;
      if (s.battery != null) {
        const b = s.battery;
        const color = s.charging ? "var(--green-2)" : b <= 20 ? "var(--red)" : b <= 40 ? "var(--amber)" : "var(--green-2)";
        fourth.set(s.charging ? "Battery ⚡" : "Battery", `${b}%`, b, color);
      } else {
        const total = s.netDown + s.netUp;
        // A desktop has no battery: show how busy the network is instead,
        // on a 10 MB/s scale.
        fourth.set("Network", rate(total), (total / (10 * 1024 ** 2)) * 100, "var(--cyan)");
      }

      // Rebuild the list only when names change, and never while a row is
      // asking "Close …?", or the question would vanish under the cursor.
      if (apps.querySelector(".confirm")) return;
      const list = State.topApps.slice(0, 4);
      const key = list.map((a) => a.name).join("|");
      if (key !== appsKey) {
        appsKey = key;
        clear(apps);
        for (const a of list) apps.append(appRow(a, actions));
        if (list.length === 0) apps.append(h("div", { class: "td-empty", text: "Measuring…" }));
      } else {
        // Same apps: just refresh the numbers in place.
        list.forEach((a, i) => {
          const row = apps.children[i] as HTMLElement | undefined;
          if (!row) return;
          const cpuEl = row.querySelector(".ap-cpu") as HTMLElement | null;
          const memEl = row.querySelector(".ap-mem") as HTMLElement | null;
          if (cpuEl) {
            cpuEl.textContent = `${a.cpu.toFixed(a.cpu < 10 ? 1 : 0)}%`;
            cpuEl.style.color = a.cpu >= 50 ? "var(--red)" : a.cpu >= 20 ? "var(--amber)" : "";
          }
          if (memEl) memEl.textContent = a.memory >= GB ? `${gb(a.memory)} GB` : `${Math.round(a.memory / 1024 ** 2)} MB`;
        });
      }
    },
  };
}
