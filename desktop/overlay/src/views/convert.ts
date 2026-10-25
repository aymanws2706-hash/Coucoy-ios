// Personal build: the Convert card after a file drop. The formats burst out of
// the droplet as glass bubbles in an arc; tapping one sends it back into the
// droplet, which "digests" it, and the new file pops out when it's ready.

import { h, clear } from "./dom";
import { Bridge } from "../core/bridge";
import { State } from "../core/state";
import type { ViewActions, ViewHost } from "./views";

type Phase =
  | { kind: "pick" }
  | { kind: "working"; label: string }
  | { kind: "done"; path: string }
  | { kind: "error"; message: string; needsFfmpeg: boolean; ext: string; label: string };

/** A colour per format family, for the bubble's tint. */
const TINT: Record<string, string> = {
  pdf: "#ff5a5f", jpg: "#ff9f43", jpeg: "#ff9f43", png: "#4dabf7", webp: "#38d9a9", ico: "#b197fc",
  bmp: "#91a7ff", gif: "#ffd43b", tiff: "#91a7ff", docx: "#4c8dff", txt: "#adb5bd", rtf: "#748ffc",
  odt: "#74c0fc", xlsx: "#40c057", csv: "#69db7c", ods: "#8ce99a", pptx: "#ff922b", mp3: "#f783ac",
  wav: "#e599f7", m4a: "#faa2c1", flac: "#da77f2", ogg: "#cc5de8", mp4: "#9775fa", webm: "#845ef7",
  mov: "#7950f2", more: "#dee2e6",
};

const SPRING = "cubic-bezier(0.34, 1.56, 0.64, 1)";

const calm = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export function buildConvert(actions: ViewActions): ViewHost {
  const title = h("div", { class: "title cv-title" });
  const stage = h("div", { class: "cv-stage" });
  const foot = h("div", { class: "sub cv-foot" });
  const el = h(
    "div",
    { class: "view" },
    h("div", { class: "card" }, h("div", { class: "cv-wrap" }, title, stage, foot)),
  );

  let source = "";
  let targets: { ext: string; label: string }[] = [];
  let phase: Phase = { kind: "pick" };
  let drawn = "";

  const fileName = () => State.droppedFile?.name ?? source.split(/[\\/]/).pop() ?? "file";

  /** Where the droplet is, relative to an element's centre (for fly-in/out). */
  function fromDroplet(node: HTMLElement): { dx: number; dy: number } {
    const bot = document.getElementById("bot-canvas")?.getBoundingClientRect();
    const r = node.getBoundingClientRect();
    if (!bot || r.width === 0) return { dx: -160, dy: 0 };
    const bx = bot.left + bot.width / 2;
    // The canvas carries extra particle room on top; the body is the square below it.
    const by = bot.bottom - bot.width / 2;
    return { dx: bx - (r.left + r.width / 2), dy: by - (r.top + r.height / 2) };
  }

  /** Pops `nodes` out of the droplet, one after another. */
  function burst(nodes: HTMLElement[]) {
    if (calm()) return;
    for (const n of nodes) {
      const { dx, dy } = fromDroplet(n);
      n.style.transition = "none";
      n.style.transform = `translate(${dx}px, ${dy}px) scale(0.15)`;
      n.style.opacity = "0";
    }
    // Two frames: the start position must be painted before the transition.
    requestAnimationFrame(() =>
      requestAnimationFrame(() => {
        nodes.forEach((n, i) => {
          n.style.transition = `transform 560ms ${SPRING} ${i * 55}ms, opacity 220ms ease-out ${i * 55}ms`;
          n.style.transform = "";
          n.style.opacity = "1";
        });
      }),
    );
  }

  function choose(bubble: HTMLElement, all: HTMLElement[], ext: string, label: string) {
    actions.blip();
    if (calm()) return void run(ext, label);
    // The chosen one flies back into the droplet; the rest drift off.
    const { dx, dy } = fromDroplet(bubble);
    bubble.style.transition = `transform 420ms cubic-bezier(0.55, 0, 0.75, 0.2), opacity 380ms ease-in`;
    bubble.style.transform = `translate(${dx}px, ${dy}px) scale(0.2)`;
    bubble.style.opacity = "0";
    all.filter((b) => b !== bubble).forEach((b, i) => {
      b.style.transition = `transform 360ms ease-in ${i * 25}ms, opacity 300ms ease-in ${i * 25}ms`;
      b.style.transform = "translateY(14px) scale(0.6)";
      b.style.opacity = "0";
    });
    window.setTimeout(() => void run(ext, label), 380);
  }

  async function run(ext: string, label: string) {
    phase = { kind: "working", label };
    State.stateOverride = "working";
    State.notify();
    try {
      const out = await Bridge.convertFile(source, ext);
      phase = { kind: "done", path: out };
      State.stateOverride = "finished";
      window.setTimeout(() => {
        if (State.stateOverride === "finished") State.stateOverride = null;
        State.notify();
      }, 2500);
    } catch (err) {
      const message = String(err).replace(/^Error:\s*/, "");
      phase = { kind: "error", message, needsFfmpeg: message === "NEEDS_FFMPEG", ext, label };
      State.stateOverride = null;
    }
    State.notify();
  }

  function askPutshi() {
    State.promptDraft = `Convert ${source} to `;
    actions.setView("prompt");
  }

  function pill(text: string, onClick: () => void, primary = false): HTMLElement {
    return h("button", { class: primary ? "btn primary" : "cv-chip", text, onclick: onClick });
  }

  function bubble(ext: string, label: string): HTMLElement {
    const tint = TINT[ext] ?? TINT.more;
    const inner = h(
      "span",
      { class: "cv-bubble-in" },
      h("b", { text: ext === "more" ? "…" : ext.toUpperCase() }),
      h("small", { text: label }),
    );
    const b = h("button", { class: "cv-bubble", title: `Convert to ${label}` }, inner);
    b.style.setProperty("--tint", tint);
    return b;
  }

  function draw() {
    clear(stage);
    stage.className = "cv-stage";
    const name = fileName();
    switch (phase.kind) {
      case "pick": {
        title.textContent = targets.length ? `Turn ${name} into…` : `Convert ${name}`;
        foot.textContent = targets.length
          ? "The new file goes next to the original."
          : "Putshi can't convert this kind of file by itself — ask in the chat.";
        const bubbles = targets.map((t) => bubble(t.ext, t.label));
        const more = bubble("more", "Other");
        bubbles.push(more);
        bubbles.forEach((b, i) => {
          // A gentle arc: the middle ones sit a little higher.
          const n = bubbles.length;
          const lift = n > 1 ? Math.sin((i / (n - 1)) * Math.PI) * 10 : 0;
          b.style.marginTop = `${12 - lift}px`;
          (b.firstChild as HTMLElement).style.animationDelay = `${(i * 0.37) % 2}s`;
          stage.append(b);
        });
        targets.forEach((t, i) =>
          bubbles[i].addEventListener("click", () => choose(bubbles[i], bubbles, t.ext, t.label)),
        );
        more.addEventListener("click", askPutshi);
        burst(bubbles);
        break;
      }
      case "working":
        title.textContent = `Turning it into ${phase.label}…`;
        foot.textContent = "Big videos and documents can take a minute.";
        stage.classList.add("working");
        stage.append(h("div", { class: "cv-progress" }, h("i")));
        break;
      case "done": {
        const out = phase.path;
        const newName = out.split(/[\\/]/).pop() ?? out;
        title.textContent = "Done";
        foot.textContent = out.replace(/[\\/][^\\/]+$/, "");
        const ext = newName.split(".").pop()?.toLowerCase() ?? "";
        const result = h("div", { class: "cv-result" }, h("span", { class: "cv-check", text: "✓" }), h("span", { text: newName }));
        result.style.setProperty("--tint", TINT[ext] ?? TINT.more);
        const buttons = h(
          "div",
          { class: "cv-actions" },
          pill("Open", () => void Bridge.openFile(out), true),
          pill("Show in folder", () => void Bridge.openFile(out, true)),
          pill("Another format", () => {
            phase = { kind: "pick" };
            State.notify();
          }),
        );
        stage.append(result, buttons);
        burst([result]);
        break;
      }
      case "error": {
        const p = phase;
        const buttons = h("div", { class: "cv-actions show" });
        if (p.needsFfmpeg) {
          title.textContent = "Audio and video need ffmpeg";
          foot.textContent = "A free converter, installed once with Windows' own installer (about a minute).";
          buttons.append(
            pill("Install ffmpeg", async () => {
              phase = { kind: "working", label: "a ready converter (installing ffmpeg)" };
              State.notify();
              try {
                await Bridge.installFfmpeg();
                await run(p.ext, p.label);
              } catch (err) {
                phase = { kind: "error", message: String(err).replace(/^Error:\s*/, ""), needsFfmpeg: false, ext: p.ext, label: p.label };
                State.notify();
              }
            }, true),
            pill("Cancel", () => actions.collapse()),
          );
        } else {
          title.textContent = "Couldn't convert it";
          foot.textContent = p.message;
          buttons.append(
            pill("Ask Putshi to do it", askPutshi, true),
            pill("Back", () => {
              phase = { kind: "pick" };
              State.notify();
            }),
          );
        }
        stage.append(buttons);
        break;
      }
    }
  }

  return {
    el,
    sync() {
      const src = State.droppedOriginal ?? State.droppedFile?.path ?? "";
      if (src !== source) {
        source = src;
        phase = { kind: "pick" };
        targets = [];
        drawn = "";
        void Bridge.convertTargets(src).then((list) => {
          targets = list ?? [];
          drawn = "";
          State.notify();
        });
      }
      // Redraw (and replay the burst) only when something actually changed,
      // and only while the card is on screen so the burst is seen.
      const key = JSON.stringify([phase, targets.length, State.view === "convert"]);
      if (key === drawn || State.view !== "convert") return;
      drawn = key;
      draw();
    },
  };
}
