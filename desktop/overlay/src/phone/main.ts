// Putshi on the phone: a page served by Coucou on the PC (through Tailscale).
// Chat with Mochi (it runs on the PC, with its tools), answer its Allow / Deny
// cards and Claude Code's, and see / control the PC: music, volume, timer,
// today, health, lock and sleep.

import "./phone.css";
import { BotEngine } from "../mochi/engine";
import { weatherIcon, when } from "../views/today";
import type { BotStateName } from "../core/layout";
import type { CalendarEvent, DeskActivity, DeskControls, NowPlaying, SystemStats, Weather } from "../core/bridge";

// ── Pairing ───────────────────────────────────────────────────────────────────

const TOKEN_KEY = "putshi.token";

function readToken(): string | null {
  const m = location.hash.match(/[#&]t=([0-9a-f]{32,})/);
  try {
    if (m) {
      localStorage.setItem(TOKEN_KEY, m[1]);
      history.replaceState(null, "", location.pathname);
    }
    return localStorage.getItem(TOKEN_KEY) ?? m?.[1] ?? null;
  } catch {
    return m?.[1] ?? null;
  }
}

const token = readToken();

async function api<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api/${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: { Authorization: `Bearer ${token ?? ""}`, "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error((data as { error?: string }).error ?? `Error ${res.status}`);
  return data as T;
}

// ── State ─────────────────────────────────────────────────────────────────────

interface IslandSnap {
  timer?: { endsAt: number; label: string } | null;
  claude?: { state: string; step: string | null; approval: { tool: string; command: string } | null } | null;
  alert?: string | null;
}

interface PhoneState {
  host: string;
  stats: SystemStats;
  weather: Weather | null;
  events: CalendarEvent[];
  nowPlaying: NowPlaying | null;
  controls: DeskControls;
  activity: DeskActivity;
  approvals: { id: number; what: string; detail: string }[];
  island: IslandSnap | null;
}

let st: PhoneState | null = null;
let online = false;
let lastError = "";
let readAt = 0;

interface Msg {
  role: "user" | "assistant" | "error";
  text: string;
}

const CHAT_KEY = "putshi.chat";
let chat: Msg[] = [];
try {
  chat = JSON.parse(localStorage.getItem(CHAT_KEY) ?? "[]");
} catch {
  chat = [];
}
let sending = false;

function saveChat() {
  try {
    localStorage.setItem(CHAT_KEY, JSON.stringify(chat.slice(-40)));
  } catch {
    /* storage full or blocked: the chat just won't survive a reload */
  }
}

// ── DOM helpers ───────────────────────────────────────────────────────────────

function el<K extends keyof HTMLElementTagNameMap>(tag: K, cls?: string, text?: string): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}

function button(label: string, cls: string, onClick: () => void): HTMLButtonElement {
  const b = el("button", cls, label);
  b.addEventListener("click", onClick);
  return b;
}

const GB = 1024 ** 3;
const pct = (a: number, b: number) => (b ? Math.round((a / b) * 100) : 0);
const mmss = (s: number) => `${Math.floor(Math.max(0, s) / 60)}:${String(Math.floor(Math.max(0, s) % 60)).padStart(2, "0")}`;

function meter(label: string, value: string, fill: number, color?: string): HTMLElement {
  const m = el("div", "meter");
  const head = el("div", "m-head");
  head.append(el("span", "m-label", label), el("span", "m-value", value));
  const bar = el("div", "m-bar");
  const i = el("i");
  const f = Math.max(0, Math.min(100, fill));
  i.style.width = `${f}%`;
  i.style.background = color ?? (f >= 90 ? "var(--red)" : f >= 70 ? "var(--amber)" : "var(--green)");
  bar.append(i);
  m.append(head, bar);
  return m;
}

// ── Layout ────────────────────────────────────────────────────────────────────

const app = document.getElementById("app")!;

const top = el("header", "top");
const mochiCanvas = el("canvas", "mochi");
const titleBox = el("div", "who");
const nameEl = el("div", "name", "Putshi");
const hostEl = el("div", "host");
titleBox.append(nameEl, hostEl);
top.append(mochiCanvas, titleBox);

const approvalsBox = el("section", "approvals");
const chatCard = el("section", "card chat");
const playCard = el("section", "card play");
const timerCard = el("section", "card timer");
const todayCard = el("section", "card today");
const pcCard = el("section", "card pcinfo");
const actionsCard = el("section", "card actions");

app.append(top, approvalsBox, chatCard, playCard, timerCard, todayCard, pcCard, actionsCard);

// ── Mochi ─────────────────────────────────────────────────────────────────────

const engine = new BotEngine();
const MOCHI = 64;
const OVERHANG = 30;
{
  const dpr = Math.min(3, devicePixelRatio || 1);
  mochiCanvas.width = MOCHI * dpr;
  mochiCanvas.height = (MOCHI + OVERHANG) * dpr;
  mochiCanvas.style.width = `${MOCHI}px`;
  mochiCanvas.style.height = `${MOCHI + OVERHANG}px`;
  engine.particleOverhang = OVERHANG;
  let last = performance.now();
  const frame = (now: number) => {
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    engine.update(dt);
    const ctx = mochiCanvas.getContext("2d");
    if (ctx) {
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, MOCHI, MOCHI + OVERHANG);
      engine.draw(ctx, MOCHI, MOCHI + OVERHANG);
    }
    tickLive();
    requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
  mochiCanvas.addEventListener("click", () => engine.triggerEmote("love"));
}

function mochiState(): BotStateName {
  if (!online) return "sleeping";
  if (sending) return "thinking";
  if (st?.approvals.length || st?.island?.claude?.approval) return "approval";
  const c = st?.island?.claude?.state;
  if (c === "working" || c === "thinking") return c;
  return "idle";
}

// ── Approvals ─────────────────────────────────────────────────────────────────

let approvalsKey = "";
function renderApprovals() {
  const list = st?.approvals ?? [];
  const cc = st?.island?.claude?.approval ?? null;
  const key = JSON.stringify([list.map((a) => a.id), cc]);
  if (key === approvalsKey) return;
  approvalsKey = key;
  approvalsBox.replaceChildren();
  for (const a of list) {
    const card = el("div", "card ask");
    card.append(el("div", "ask-who", `Mochi wants to: ${a.what}`), el("code", "ask-code", a.detail));
    const row = el("div", "row");
    row.append(
      button("Deny", "btn ghost", () => void decide(card, () => api("approve", { id: a.id, allow: false }))),
      button("Allow", "btn", () => void decide(card, () => api("approve", { id: a.id, allow: true }))),
    );
    card.append(row);
    approvalsBox.append(card);
  }
  if (cc) {
    const card = el("div", "card ask");
    card.append(el("div", "ask-who", "Claude Code needs permission"), el("code", "ask-code", cc.command || cc.tool));
    const row = el("div", "row");
    row.append(
      button("Deny", "btn ghost", () => void decide(card, () => api("claude", { decision: "deny" }))),
      button("Allow", "btn", () => void decide(card, () => api("claude", { decision: "allow" }))),
    );
    card.append(row);
    approvalsBox.append(card);
  }
}

async function decide(card: HTMLElement, call: () => Promise<unknown>) {
  card.classList.add("busy");
  try {
    await call();
  } catch (err) {
    alertMsg(String(err));
  }
  void refresh();
}

// ── Chat ──────────────────────────────────────────────────────────────────────

const log = el("div", "log");
const form = el("form", "ask-bar");
const input = el("input", "input") as HTMLInputElement;
input.placeholder = "Ask Mochi… (it works on your PC)";
input.enterKeyHint = "send";
const sendBtn = el("button", "send", "↑");
sendBtn.type = "submit";
const reset = button("New", "mini", () => {
  chat = [];
  saveChat();
  renderChat();
  void api("chat/reset", {}).catch(() => {});
});
form.append(input, sendBtn);
const chatHead = el("div", "card-head");
chatHead.append(el("span", "", "Mochi"), reset);
chatCard.append(chatHead, log, form);

function renderChat() {
  log.replaceChildren();
  for (const m of chat.slice(-12)) log.append(el("div", `msg ${m.role}`, m.text));
  if (sending) {
    const t = el("div", "msg assistant typing");
    t.append(el("i"), el("i"), el("i"));
    log.append(t);
  }
  log.classList.toggle("empty", chat.length === 0 && !sending);
  if (chat.length === 0 && !sending) {
    log.append(el("div", "hint", "Try: “what's using my CPU?”, “find the PDF I downloaded yesterday”, “pause the music”, “set a 20 min timer”."));
  }
  log.scrollTop = log.scrollHeight;
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text || sending) return;
  input.value = "";
  chat.push({ role: "user", text });
  sending = true;
  renderChat();
  try {
    const r = await api<{ text: string }>("chat", { text });
    chat.push({ role: "assistant", text: r.text });
    engine.triggerEmote("happy");
  } catch (err) {
    chat.push({ role: "error", text: String(err).replace(/^Error:\s*/, "") });
  }
  sending = false;
  saveChat();
  renderChat();
});

// ── Now playing + volume ──────────────────────────────────────────────────────

const npTitle = el("div", "np-title");
const npArtist = el("div", "np-artist");
const npBar = el("div", "np-bar");
const npFill = el("i");
npBar.append(npFill);
const npTimes = el("div", "np-times");
const npPrev = button("⏮", "round", () => void media("previous"));
const npPlay = button("⏯", "round big", () => void media("toggle"));
const npNext = button("⏭", "round", () => void media("next"));
const npRow = el("div", "row center");
npRow.append(npPrev, npPlay, npNext);
const volRow = el("div", "row vol");
const volMute = button("🔊", "mini", () => void api("mute", { mic: false, muted: !(st?.controls.muted ?? false) }).then(refresh));
const vol = el("input", "slider") as HTMLInputElement;
vol.type = "range";
vol.min = "0";
vol.max = "100";
vol.addEventListener("change", () => void api("volume", { percent: Number(vol.value) }));
volRow.append(volMute, vol);
playCard.append(npTitle, npArtist, npBar, npTimes, npRow, volRow);

async function media(action: string) {
  try {
    await api("media", { action });
  } catch (err) {
    alertMsg(String(err));
  }
  window.setTimeout(() => void refresh(), 400);
}

function renderPlay() {
  const p = st?.nowPlaying;
  npTitle.textContent = p ? p.title : "Nothing playing";
  npArtist.textContent = p ? [p.artist, p.app].filter(Boolean).join(" · ") : "Music and videos on the PC show up here.";
  npPlay.textContent = p?.playing ? "⏸" : "▶";
  const c = st?.controls;
  if (c && document.activeElement !== vol) vol.value = String(c.volume ?? 0);
  vol.disabled = c?.volume == null;
  volMute.textContent = c?.muted ? "🔇" : "🔊";
}

// ── Timer ─────────────────────────────────────────────────────────────────────

const timerText = el("div", "timer-text");
const timerRow = el("div", "row");
timerCard.append(timerText, timerRow);
let timerKey = "";

function renderTimer() {
  const t = st?.island?.timer;
  const key = t ? "run" : "idle";
  if (key !== timerKey) {
    timerKey = key;
    timerRow.replaceChildren();
    if (t) {
      timerRow.append(button("Stop", "btn ghost", () => void api("timer", { minutes: 0 }).then(refresh)));
    } else {
      for (const m of [5, 15, 25, 50]) {
        timerRow.append(button(`${m} min`, "chip", () => void api("timer", { minutes: m, label: m === 25 ? "Focus" : "" }).then(refresh)));
      }
    }
  }
}

// ── Today ─────────────────────────────────────────────────────────────────────

function renderToday() {
  todayCard.replaceChildren();
  const w = st?.weather;
  const head = el("div", "today-head");
  head.append(
    el("span", "big", w ? `${weatherIcon(w.code, w.isDay)} ${Math.round(w.temp)}°` : "—"),
    el("span", "dim", w ? `${w.city}  ·  ${Math.round(w.high)}° / ${Math.round(w.low)}°` : "Weather unavailable"),
  );
  todayCard.append(head);
  if (w) {
    const hours = el("div", "hours");
    for (const x of w.hours) {
      const c = el("div", "hour");
      c.append(el("span", "dim", `${x.hour}h`), el("span", "", weatherIcon(x.code, x.hour >= 7 && x.hour < 20)), el("b", "", `${Math.round(x.temp)}°`));
      hours.append(c);
    }
    todayCard.append(hours);
  }
  const events = st?.events.slice(0, 4) ?? [];
  if (events.length === 0) todayCard.append(el("div", "dim small", "No events coming up (or no calendar link in Coucou › Settings)."));
  for (const e of events) {
    const row = el("div", "event");
    row.append(el("span", "when", when(e)), el("span", "title", e.title));
    todayCard.append(row);
  }
}

// ── PC ────────────────────────────────────────────────────────────────────────

function renderPc() {
  pcCard.replaceChildren();
  const s = st?.stats;
  if (!s) return;
  const head = el("div", "card-head");
  head.append(el("span", "", "This PC"));
  const a = st!.activity;
  const flags = el("span", "flags");
  if (a.micInUse) flags.append(el("i", "dot mic"));
  if (a.cameraInUse) flags.append(el("i", "dot cam"));
  head.append(flags);
  pcCard.append(head);
  const grid = el("div", "meters");
  grid.append(
    meter("CPU", `${Math.round(s.cpu)}%`, s.cpu),
    meter("Memory", `${pct(s.memUsed, s.memTotal)}%`, pct(s.memUsed, s.memTotal)),
    meter("Free on C:", `${Math.round((s.diskTotal - s.diskUsed) / GB)} GB`, pct(s.diskUsed, s.diskTotal)),
    s.battery != null
      ? meter(s.charging ? "Battery ⚡" : "Battery", `${s.battery}%`, s.battery, s.battery <= 20 && !s.charging ? "var(--red)" : "var(--green)")
      : meter("Network ↓", `${(s.netDown / 1024 ** 2).toFixed(1)} MB/s`, (s.netDown / (10 * 1024 ** 2)) * 100, "var(--cyan)"),
  );
  pcCard.append(grid);
  for (const d of a.downloads) pcCard.append(el("div", "small", `⬇ ${d.name}  ${Math.round(d.bytes / 1024 ** 2)} MB`));
  const cc = st?.island?.claude;
  if (cc && cc.state !== "idle") pcCard.append(el("div", "small", `Claude Code: ${cc.state}${cc.step ? " — " + cc.step : ""}`));
  if (st?.island?.alert) pcCard.append(el("div", "small warn", `⚠️ ${st.island.alert}`));
}

// ── Actions ───────────────────────────────────────────────────────────────────

{
  const head = el("div", "card-head");
  head.append(el("span", "", "PC"));
  const row = el("div", "row");
  const lock = button("Lock", "chip", () => void api("shortcut", { which: "lock" }).then(() => alertMsg("Locked.")).catch((e) => alertMsg(String(e))));
  const sleep = button("Sleep", "chip", () => {
    if (sleep.dataset.armed !== "1") {
      sleep.dataset.armed = "1";
      sleep.textContent = "Tap again to sleep";
      window.setTimeout(() => {
        sleep.dataset.armed = "";
        sleep.textContent = "Sleep";
      }, 4000);
      return;
    }
    void api("shortcut", { which: "sleep" }).catch((e) => alertMsg(String(e)));
  });
  const mic = button("Mic on / off", "chip", () => void api("mute", { mic: true, muted: !(st?.controls.micMuted ?? false) }).then(refresh));
  row.append(lock, sleep, mic);
  actionsCard.append(head, row);
}

// ── Status / errors ───────────────────────────────────────────────────────────

const toast = el("div", "toast");
document.body.append(toast);
let toastTimer = 0;
function alertMsg(text: string) {
  toast.textContent = text.replace(/^Error:\s*/, "");
  toast.classList.add("on");
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => toast.classList.remove("on"), 3000);
}

/** Things that move between refreshes: song position, timer countdown. */
function tickLive() {
  const p = st?.nowPlaying;
  if (p && p.duration > 0) {
    const pos = Math.min(p.duration, p.position + (p.playing ? (performance.now() - readAt) / 1000 : 0));
    npFill.style.width = `${(pos / p.duration) * 100}%`;
    npTimes.textContent = `${mmss(pos)}  /  ${mmss(p.duration)}`;
    npBar.style.visibility = "";
  } else {
    npBar.style.visibility = "hidden";
    npTimes.textContent = "";
  }
  const t = st?.island?.timer;
  timerText.textContent = t
    ? `⏱ ${mmss((t.endsAt - Date.now()) / 1000)}${t.label ? "  " + t.label : ""}`
    : "⏱ Timer";
}

function render() {
  hostEl.textContent = online ? `Connected to ${st?.host || "your PC"}` : lastError || "Connecting…";
  hostEl.classList.toggle("off", !online);
  engine.setState(mochiState());
  renderApprovals();
  renderPlay();
  renderTimer();
  renderToday();
  renderPc();
}

async function refresh() {
  if (!token) return;
  try {
    st = await api<PhoneState>("state");
    readAt = performance.now();
    online = true;
    lastError = "";
  } catch (err) {
    online = false;
    lastError = String(err).replace(/^Error:\s*/, "").replace(/^TypeError:.*/, "Can't reach the PC. Is it on, with Tailscale connected?");
  }
  render();
}

// ── Start ─────────────────────────────────────────────────────────────────────

if (!token) {
  app.replaceChildren(top, el("section", "card"));
  const card = app.lastElementChild as HTMLElement;
  card.append(
    el("div", "big", "Not paired yet"),
    el("p", "dim", "On the PC: Coucou › Settings › Phone › Turn on, then scan the QR code with the iPhone camera."),
  );
  hostEl.textContent = "";
  engine.setState("sleeping");
} else {
  renderChat();
  render();
  void refresh();
  window.setInterval(() => {
    if (document.visibilityState === "visible") void refresh();
  }, 3000);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") void refresh();
  });
}
