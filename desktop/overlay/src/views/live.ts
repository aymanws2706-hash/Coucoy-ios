// Personal build: the Live panel — Barça and Morocco, Formula 1, and the
// markets (indices, crypto, what's trending). Data comes from live.rs.

import { h, clear } from "./dom";
import type { LiveData, LiveMatch, LiveQuote } from "../core/bridge";
import { State } from "../core/state";
import type { ViewActions, ViewHost } from "./views";

function dayTime(ms: number): string {
  const d = new Date(ms);
  const now = new Date();
  const tomorrow = new Date(now.getTime() + 86400000);
  const time = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  if (d.toDateString() === now.toDateString()) return `Today ${time}`;
  if (d.toDateString() === tomorrow.toDateString()) return `Tmrw ${time}`;
  return `${d.toLocaleDateString([], { weekday: "short" })} ${d.getDate()} ${time}`;
}

function countdown(ms: number): string {
  const mins = Math.round((ms - Date.now()) / 60000);
  if (mins <= 0) return "now";
  if (mins < 60) return `in ${mins} min`;
  if (mins < 48 * 60) return `in ${Math.round(mins / 60)} h`;
  return `in ${Math.round(mins / 1440)} days`;
}

/** "Barcelona 2–1 Real Madrid". */
export function scoreLine(m: LiveMatch): string {
  return `${m.home} ${m.homeScore ?? 0}–${m.awayScore ?? 0} ${m.away}`;
}

function price(q: LiveQuote): string {
  const p = q.price;
  if (p >= 1000) return p.toLocaleString([], { maximumFractionDigits: 0 });
  if (p >= 1) return p.toLocaleString([], { maximumFractionDigits: 2 });
  return p.toPrecision(3);
}

export function buildLive(_actions: ViewActions): ViewHost {
  const foot = h("div", { class: "lv-col" });
  const f1 = h("div", { class: "lv-col" });
  const mk = h("div", { class: "lv-col" });
  const note = h("div", { class: "lv-note" });
  const el = h(
    "div",
    { class: "view" },
    h("div", { class: "card" }, h("div", { class: "lv" }, h("div", { class: "lv-cols" }, foot, f1, mk), note)),
  );
  let drawn = -1;

  const head = (icon: string, text: string) => h("div", { class: "lv-head" }, h("span", { text: icon }), h("b", { text }));
  const row = (a: string, b = "", cls = "") =>
    h("div", { class: `lv-row ${cls}` }, h("span", { class: "lv-a", text: a }), h("span", { class: "lv-b", text: b }));

  function draw(d: LiveData) {
    clear(foot);
    clear(f1);
    clear(mk);
    // Football
    foot.append(head("⚽", "Football"));
    for (const t of d.teams) {
      foot.append(h("div", { class: "lv-team", text: t.name }));
      if (t.live) {
        foot.append(row(scoreLine(t.live), t.live.detail, "live"));
      } else {
        if (t.last) foot.append(row(scoreLine(t.last), t.last.competition, "dim"));
        if (t.next) {
          // "vs Senegal" from our side's point of view.
          const ours = t.name === "Barça" ? /barc/i : new RegExp(t.name, "i");
          const opp = ours.test(t.next.home) ? t.next.away : t.next.home;
          foot.append(row(`vs ${opp}`, dayTime(t.next.startMs)));
        }
      }
      if (!t.live && !t.last && !t.next) foot.append(row("No matches found", "", "dim"));
    }
    // Formula 1
    f1.append(head("🏎️", "Formula 1"));
    const r = d.f1;
    if (r) {
      if (r.nextRace) {
        f1.append(row(r.nextRace.replace(" Grand Prix", " GP"), r.nextMs ? countdown(r.nextMs) : ""));
        if (r.nextMs) f1.append(row(dayTime(r.nextMs), "", "dim"));
      }
      if (r.lastRace && r.lastPodium.length) {
        f1.append(h("div", { class: "lv-sub", text: "Last race" }));
        f1.append(row(`🏆 ${r.lastPodium.join(" · ")}`, r.lastRace.replace(" Grand Prix", ""), "dim"));
      }
      if (r.standings.length) {
        f1.append(h("div", { class: "lv-sub", text: "Standings" }));
        f1.append(row(r.standings.map(([c, p]) => `${c} ${Math.round(p)}`).join(" · "), "", "small"));
      }
    }
    // Markets
    mk.append(head("📈", "Markets"));
    const quote = (q: LiveQuote) => {
      const up = q.changePct >= 0;
      const e = row(q.name.length > 14 ? q.symbol : q.name, `${price(q)}  ${up ? "▲" : "▼"}${Math.abs(q.changePct).toFixed(1)}%`, up ? "up" : "down");
      e.title = `${q.name} (${q.symbol})`;
      return e;
    };
    for (const q of d.markets.slice(0, 3)) mk.append(quote(q));
    const hot = [...d.trending.slice(0, 2), ...d.cryptoTrending.slice(0, 2)];
    if (hot.length) {
      mk.append(h("div", { class: "lv-sub", text: "🔥 Trending" }));
      for (const q of hot) mk.append(quote(q));
    }
    note.textContent = d.errors.length
      ? d.errors.join(" · ")
      : d.at
        ? `Updated ${new Date(d.at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`
        : "Loading…";
  }

  return {
    el,
    sync() {
      const d = State.live;
      if (State.view !== "live" || !d || d.at === drawn) return;
      drawn = d.at;
      draw(d);
    },
  };
}
