// Personal build: the Controls panel (now playing, volume, mic, brightness,
// Wi-Fi, shortcuts) and the Clipboard panel.

import { h, svg, clear } from "./dom";
import { ICONS } from "./icons";
import { Bridge } from "../core/bridge";
import { State } from "../core/state";
import type { ViewActions, ViewHost } from "./views";

function mmss(secs: number): string {
  const s = Math.max(0, Math.floor(secs));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/** Where the song is now, moving on between samples while it plays. */
export function livePosition(): number {
  const p = State.nowPlaying;
  if (!p) return 0;
  const extra = p.playing ? (performance.now() - State.nowPlayingAt) / 1000 : 0;
  return p.duration > 0 ? Math.min(p.duration, p.position + extra) : 0;
}

function slider(onCommit: (v: number) => void): HTMLInputElement {
  const el = h("input", { type: "range", min: "0", max: "100", step: "1", class: "ct-slider" }) as HTMLInputElement;
  // Volume follows the finger; brightness (slow, through WMI) only on release.
  el.addEventListener("change", () => onCommit(Number(el.value)));
  return el;
}

export function buildControls(actions: ViewActions): ViewHost {
  /** Shows a short message, then comes back here. */
  const note = (text: string) => {
    State.noteMessage = text;
    actions.setView("note");
    window.setTimeout(() => {
      if (State.view === "note") actions.setView("controls");
    }, 2600);
  };

  // ── Now playing ──
  const title = h("div", { class: "np-title" });
  const artist = h("div", { class: "np-artist" });
  const barFill = h("i");
  const bar = h("div", { class: "np-bar" }, barFill);
  const elapsed = h("span");
  const total = h("span");
  const times = h("div", { class: "np-times" }, elapsed, total);
  const prev = h("button", { class: "np-btn", title: "Previous" }, svg(ICONS.previous, 13));
  const play = h("button", { class: "np-btn big", title: "Play / pause" });
  const next = h("button", { class: "np-btn", title: "Next" }, svg(ICONS.next, 13));
  const media = h("div", { class: "np" }, title, artist, bar, times, h("div", { class: "np-row" }, prev, play, next));

  const send = (action: "toggle" | "next" | "previous") => {
    actions.blip();
    void Bridge.mediaControl(action).then(async () => {
      const p = await Bridge.nowPlaying();
      State.nowPlaying = p;
      State.nowPlayingAt = performance.now();
      State.notify();
    });
  };
  prev.addEventListener("click", () => send("previous"));
  play.addEventListener("click", () => send("toggle"));
  next.addEventListener("click", () => send("next"));

  // ── Sliders and toggles ──
  const volIcon = h("button", { class: "ct-icon", title: "Mute" });
  const vol = slider(() => {});
  vol.addEventListener("input", () => void Bridge.setVolume(Number(vol.value)));
  volIcon.addEventListener("click", () => {
    const muted = !(State.controls?.muted ?? false);
    if (State.controls) State.controls.muted = muted;
    void Bridge.setMute(false, muted);
    State.notify();
  });
  const volRow = h("div", { class: "ct-row" }, volIcon, vol);

  const sunIcon = h("span", { class: "ct-icon static" }, svg(ICONS.sun, 13, { stroke: 1.8 }));
  const bright = slider((v) => {
    Bridge.setBrightness(v).catch((err) => note(String(err).replace(/^Error:\s*/, "")));
  });
  const brightRow = h("div", { class: "ct-row" }, sunIcon, bright);

  const mic = h("button", { class: "ct-chip" });
  mic.addEventListener("click", () => {
    const muted = !(State.controls?.micMuted ?? false);
    if (State.controls) State.controls.micMuted = muted;
    void Bridge.setMute(true, muted);
    actions.blip();
    State.notify();
  });
  const wifi = h("span", { class: "ct-wifi" });
  const chips = h("div", { class: "ct-row" }, mic, wifi);

  // ── Shortcuts ──
  const shortcuts: [string, string][] = [
    ["lock", "Lock"],
    ["sleep", "Sleep"],
    ["screenshot", "Screenshot"],
    ["downloads", "Downloads"],
    ["taskmgr", "Task Manager"],
    ["settings", "Settings"],
  ];
  const shortcutRow = h("div", { class: "ct-shortcuts" });
  for (const [id, label] of shortcuts) {
    const b = h("button", { class: "ct-sc", text: label });
    b.addEventListener("click", () => {
      if (id === "sleep" && b.dataset.armed !== "1") {
        // Sleep is the only one that interrupts you: ask once.
        b.dataset.armed = "1";
        b.textContent = "Sleep now?";
        b.classList.add("armed");
        window.setTimeout(() => {
          b.dataset.armed = "";
          b.textContent = label;
          b.classList.remove("armed");
        }, 4000);
        return;
      }
      actions.blip();
      if (id === "screenshot") actions.collapse();
      Bridge.shortcut(id).catch((err) => note(String(err).replace(/^Error:\s*/, "")));
    });
    shortcutRow.append(b);
  }

  const right = h("div", { class: "ct-right" }, volRow, brightRow, chips);
  const body = h(
    "div",
    { class: "ct" },
    h("div", { class: "ct-top" }, media, right),
    shortcutRow,
  );

  return {
    el: h("div", { class: "view" }, h("div", { class: "card" }, body)),
    tick() {
      // The progress bar moves every frame while a song plays.
      const p = State.nowPlaying;
      if (!p || p.duration <= 0) return;
      const pos = livePosition();
      barFill.style.width = `${(pos / p.duration) * 100}%`;
      elapsed.textContent = mmss(pos);
    },
    sync() {
      const p = State.nowPlaying;
      media.classList.toggle("empty", !p);
      if (p) {
        title.textContent = p.title;
        artist.textContent = [p.artist, p.app].filter(Boolean).join("  ·  ");
        clear(play);
        play.append(svg(p.playing ? ICONS.pause : ICONS.play, 15));
        const hasTime = p.duration > 0;
        bar.style.visibility = hasTime ? "" : "hidden";
        times.style.visibility = hasTime ? "" : "hidden";
        total.textContent = hasTime ? mmss(p.duration) : "";
      } else {
        title.textContent = "Nothing playing";
        artist.textContent = "Spotify, YouTube and other players show up here.";
        clear(play);
        play.append(svg(ICONS.play, 15));
        bar.style.visibility = "hidden";
        times.style.visibility = "hidden";
      }

      const c = State.controls;
      const sliding = document.activeElement === vol || document.activeElement === bright;
      if (c && !sliding) {
        vol.disabled = c.volume == null;
        vol.value = String(c.volume ?? 0);
        bright.value = String(c.brightness ?? 50);
      }
      clear(volIcon);
      volIcon.append(svg(c?.muted ? ICONS.speakerOff : ICONS.speakerOn, 13));
      brightRow.style.display = c?.brightness == null ? "none" : "";
      vol.style.opacity = c?.muted ? "0.4" : "1";

      mic.textContent = c?.micMuted == null ? "No mic" : c.micMuted ? "🎙️ Mic off" : "🎙️ Mic on";
      mic.classList.toggle("off", c?.micMuted === true);
      mic.disabled = c?.micMuted == null;
      wifi.textContent = c?.wifi ? `📶 ${c.wifi}${c.wifiSignal != null ? `  ${c.wifiSignal}%` : ""}` : "Wired or offline";
    },
  };
}

export function buildClipboard(actions: ViewActions): ViewHost {
  const list = h("div", { class: "cb-list" });
  const clearBtn = h("button", { class: "ct-sc", text: "Clear" });
  const head = h(
    "div",
    { class: "cb-head" },
    h("span", { text: "Recently copied" }),
    h("span", { class: "cb-hint", text: "Kept in memory only · click to copy again" }),
    clearBtn,
  );
  clearBtn.addEventListener("click", () => {
    actions.blip();
    State.clipboard = [];
    void Bridge.clipboardClear();
    State.notify();
  });

  let key: string | null = null;
  return {
    el: h("div", { class: "view" }, h("div", { class: "card" }, h("div", { class: "cb" }, head, list))),
    sync() {
      const items = State.clipboard.slice(0, 5);
      const k = items.join("\u0000");
      if (k === key) return;
      key = k;
      clear(list);
      if (items.length === 0) {
        list.append(h("div", { class: "td-empty", text: "Copy some text and it shows up here." }));
        return;
      }
      items.forEach((text, i) => {
        const row = h("button", { class: "cb-item", text: text.replace(/\s+/g, " ").trim() });
        row.title = text.length > 400 ? text.slice(0, 400) + "…" : text;
        row.addEventListener("click", () => {
          void Bridge.clipboardCopy(i);
          actions.blip();
          row.classList.add("copied");
          window.setTimeout(() => row.classList.remove("copied"), 900);
        });
        list.append(row);
      });
    },
  };
}
