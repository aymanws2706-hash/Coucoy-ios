// Personal build: the Convert card after a file drop — pick a format, see it
// work, then open the new file or show it in its folder.

import { h, clear } from "./dom";
import { Bridge } from "../core/bridge";
import { State } from "../core/state";
import type { ViewActions, ViewHost } from "./views";

type Phase =
  | { kind: "pick" }
  | { kind: "working"; label: string }
  | { kind: "done"; path: string }
  | { kind: "error"; message: string; needsFfmpeg: boolean; ext: string; label: string };

export function buildConvert(actions: ViewActions): ViewHost {
  const title = h("div", { class: "title" });
  const sub = h("div", { class: "sub" });
  const row = h("div", { class: "cv-row" });
  const el = h(
    "div",
    { class: "view" },
    h("div", { class: "card" }, h("div", { class: "stack", style: "padding:0 18px 0 112px" }, title, sub, row)),
  );

  let source = "";
  let targets: { ext: string; label: string }[] = [];
  let phase: Phase = { kind: "pick" };
  let drawn = "";

  const fileName = () => State.droppedFile?.name ?? source.split(/[\\/]/).pop() ?? "file";

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

  function chip(text: string, onClick: () => void, primary = false): HTMLElement {
    return h("button", { class: primary ? "btn primary" : "cv-chip", text, onclick: onClick });
  }

  function draw() {
    clear(row);
    const name = fileName();
    switch (phase.kind) {
      case "pick":
        title.textContent = `Convert ${name}`;
        sub.textContent = targets.length
          ? "Pick a format. The new file goes next to the original."
          : "Putshi can't convert this kind of file by itself.";
        for (const t of targets) row.append(chip(t.label, () => void run(t.ext, t.label)));
        row.append(chip(targets.length ? "Something else…" : "Ask Putshi to do it", askPutshi));
        break;
      case "working":
        title.textContent = `Converting to ${phase.label}…`;
        sub.textContent = "Big videos and documents can take a minute.";
        break;
      case "done": {
        const out = phase.path;
        title.textContent = `Saved ${out.split(/[\\/]/).pop()}`;
        sub.textContent = out.replace(/[\\/][^\\/]+$/, "");
        row.append(
          chip("Open", () => void Bridge.openFile(out), true),
          chip("Show in folder", () => void Bridge.openFile(out, true)),
          chip("Another format", () => {
            phase = { kind: "pick" };
            State.notify();
          }),
        );
        break;
      }
      case "error": {
        const p = phase;
        if (p.needsFfmpeg) {
          title.textContent = "Audio and video need ffmpeg";
          sub.textContent = "A free converter, installed once with Windows' own installer (about a minute).";
          row.append(
            chip("Install ffmpeg", async () => {
              phase = { kind: "working", label: "install ffmpeg" };
              State.notify();
              try {
                await Bridge.installFfmpeg();
                await run(p.ext, p.label);
              } catch (err) {
                phase = { kind: "error", message: String(err).replace(/^Error:\s*/, ""), needsFfmpeg: false, ext: p.ext, label: p.label };
                State.notify();
              }
            }, true),
            chip("Cancel", () => actions.collapse()),
          );
        } else {
          title.textContent = "Couldn't convert it";
          sub.textContent = p.message;
          row.append(chip("Ask Putshi to do it", askPutshi, true), chip("Back", () => {
            phase = { kind: "pick" };
            State.notify();
          }));
        }
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
      const key = JSON.stringify([phase, targets.length]);
      if (key === drawn) return;
      drawn = key;
      draw();
    },
  };
}
