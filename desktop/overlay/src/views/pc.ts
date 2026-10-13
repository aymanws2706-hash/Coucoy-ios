// Personal build: the desktop panel the island opens on, and the clock and
// stats line shown in the compact notch.

import "./pc.css";
import { h } from "./dom";
import { State } from "../core/state";
import type { SystemStats } from "../core/bridge";
import type { ViewActions, ViewHost } from "./views";

const GB = 1024 ** 3;

function pct(used: number, total: number): number {
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

export function buildPc(actions: ViewActions): ViewHost {
  const time = h("div", { class: "pc-time" });
  const date = h("div", { class: "pc-date" });
  const net = h("div", { class: "pc-net" });
  const host = h("div", { class: "pc-host" });
  const cpu = meter();
  const mem = meter();
  const disk = meter();
  const fourth = meter();

  const body = h(
    "div",
    { class: "pc" },
    h("div", { class: "pc-clock" }, time, date, net, host),
    h("div", { class: "pc-meters" }, cpu.el, mem.el, disk.el, fourth.el),
  );
  const card = h("div", { class: "card" }, body);
  card.addEventListener("dblclick", () => actions.openSettingsWindow());

  return {
    el: h("div", { class: "view" }, card),
    sync() {
      const now = new Date();
      time.textContent = clock(now);
      date.textContent = now.toLocaleDateString([], { weekday: "long", day: "numeric", month: "short" });

      const s: SystemStats | null = State.stats;
      if (!s) {
        net.textContent = "Reading your PC…";
        host.textContent = "";
        cpu.set("CPU", "–", 0);
        mem.set("Memory", "–", 0);
        disk.set("Disk", "–", 0);
        fourth.set("Battery", "–", 0);
        return;
      }
      net.textContent = `↓ ${rate(s.netDown)}  ↑ ${rate(s.netUp)}`;
      host.textContent = `On for ${uptime(s.uptimeSecs)}`;
      host.title = s.host;

      const c = Math.round(s.cpu);
      cpu.set("CPU", `${c}%`, c);
      const m = pct(s.memUsed, s.memTotal);
      mem.set("Memory", `${gb(s.memUsed)} / ${gb(s.memTotal)} GB`, m);
      const d = pct(s.diskUsed, s.diskTotal);
      disk.set("Disk C:", `${gb(s.diskTotal - s.diskUsed)} GB free`, d);
      if (s.battery != null) {
        const b = s.battery;
        const color = s.charging ? "var(--green-2)" : b <= 20 ? "var(--red)" : b <= 40 ? "var(--amber)" : "var(--green-2)";
        fourth.set(s.charging ? "Battery · charging" : "Battery", `${b}%`, b, color);
      } else {
        const total = s.netDown + s.netUp;
        // A desktop has no battery: show how busy the network is instead,
        // on a 10 MB/s scale.
        fourth.set("Network", rate(total), (total / (10 * 1024 ** 2)) * 100, "var(--cyan)");
      }
    },
  };
}

/** One line for the compact notch: "14:32 · CPU 12% · 82%". */
export function notchLine(): string {
  const parts = [clock()];
  const s = State.stats;
  if (s) {
    parts.push(`CPU ${Math.round(s.cpu)}%`);
    if (s.battery != null) parts.push(`${s.charging ? "⚡" : ""}${s.battery}%`);
    else parts.push(`RAM ${pct(s.memUsed, s.memTotal)}%`);
  }
  return parts.join("  ·  ");
}
