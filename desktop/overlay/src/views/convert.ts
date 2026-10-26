// Personal build: the Tools card after a file drop (or a screenshot). New
// formats and actions burst out of the droplet as glass bubbles; tapping one
// sends it back into the droplet, which "digests" it, and the result pops out:
// a new file (convert, translate, resize, compress, merge) or text (summary,
// the text in a picture).

import { h, clear } from "./dom";
import { Bridge } from "../core/bridge";
import { State } from "../core/state";
import type { ViewActions, ViewHost } from "./views";

type Option = { key: string; label: string; icon?: string };

type Phase =
  | { kind: "pick" }
  | { kind: "sub"; action: string; title: string; options: Option[] }
  | { kind: "working"; label: string }
  | { kind: "done"; path: string }
  | { kind: "text"; title: string; text: string }
  | { kind: "error"; message: string; retry: (() => Promise<void>) | null; install: "ffmpeg" | "ghostscript" | null };

/** A colour per format family, for the bubble's tint. */
const TINT: Record<string, string> = {
  pdf: "#ff5a5f", jpg: "#ff9f43", jpeg: "#ff9f43", png: "#4dabf7", webp: "#38d9a9", ico: "#b197fc",
  bmp: "#91a7ff", gif: "#ffd43b", tiff: "#91a7ff", docx: "#4c8dff", txt: "#adb5bd", rtf: "#748ffc",
  odt: "#74c0fc", xlsx: "#40c057", csv: "#69db7c", ods: "#8ce99a", pptx: "#ff922b", mp3: "#f783ac",
  wav: "#e599f7", m4a: "#faa2c1", flac: "#da77f2", ogg: "#cc5de8", mp4: "#9775fa", webm: "#845ef7",
  mov: "#7950f2", more: "#dee2e6",
  summary: "#ffd43b", translate: "#3bc9db", resize: "#69db7c", compress: "#ff8787", merge: "#b197fc",
  text: "#e9ecef", ask: "#748ffc", show: "#adb5bd",
};

const LANGS: Option[] = [
  { key: "English", label: "English", icon: "EN" },
  { key: "French", label: "Français", icon: "FR" },
  { key: "Arabic", label: "العربية", icon: "AR" },
  { key: "Spanish", label: "Español", icon: "ES" },
];

const SIZES: Option[] = [
  { key: "3840", label: "4K", icon: "3840" },
  { key: "1920", label: "Full HD", icon: "1920" },
  { key: "1280", label: "Web", icon: "1280" },
  { key: "800", label: "Small", icon: "800" },
];

const SPRING = "cubic-bezier(0.34, 1.56, 0.64, 1)";
const IMAGES = ["png", "jpg", "jpeg", "webp", "gif", "bmp", "tif", "tiff", "heic", "heif", "avif"];
const READABLE = ["pdf", "doc", "docx", "rtf", "odt", "txt", "md", "xls", "xlsx", "ppt", "pptx", "csv", ...IMAGES];

const calm = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const ext = (p: string) => (p.split(".").pop() ?? "").toLowerCase();
const nameOf = (p: string) => p.split(/[\\/]/).pop() ?? p;
const errText = (err: unknown) => String(err).replace(/^Error:\s*/, "");

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

  const fileName = () => (State.snipMode ? "your screenshot" : State.droppedFile?.name ?? nameOf(source));
  const pdfs = () => State.droppedAll.filter((p) => ext(p) === "pdf");

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
          n.style.transition = `transform 560ms ${SPRING} ${i * 50}ms, opacity 220ms ease-out ${i * 50}ms`;
          n.style.transform = "";
          n.style.opacity = "1";
        });
      }),
    );
  }

  /** The chosen bubble flies into the droplet, the rest drift off, then `then` runs. */
  function swallow(bubble: HTMLElement, then: () => void) {
    actions.blip();
    if (calm()) return then();
    const all = [...stage.querySelectorAll<HTMLElement>(".cv-bubble")];
    const { dx, dy } = fromDroplet(bubble);
    bubble.style.transition = `transform 420ms cubic-bezier(0.55, 0, 0.75, 0.2), opacity 380ms ease-in`;
    bubble.style.transform = `translate(${dx}px, ${dy}px) scale(0.2)`;
    bubble.style.opacity = "0";
    all.filter((b) => b !== bubble).forEach((b, i) => {
      b.style.transition = `transform 360ms ease-in ${i * 20}ms, opacity 300ms ease-in ${i * 20}ms`;
      b.style.transform = "translateY(14px) scale(0.6)";
      b.style.opacity = "0";
    });
    window.setTimeout(then, 380);
  }

  /** Runs a job with the droplet working; the result is a file or text. */
  async function run(label: string, job: () => Promise<{ path?: string; text?: string; title?: string }>) {
    phase = { kind: "working", label };
    State.stateOverride = "working";
    State.notify();
    try {
      const out = await job();
      phase = out.path ? { kind: "done", path: out.path } : { kind: "text", title: out.title ?? "Done", text: out.text ?? "" };
      State.stateOverride = "finished";
      window.setTimeout(() => {
        if (State.stateOverride === "finished") State.stateOverride = null;
        State.notify();
      }, 2500);
    } catch (err) {
      const message = errText(err);
      const install = message === "NEEDS_FFMPEG" ? "ffmpeg" : message === "NEEDS_GHOSTSCRIPT" ? "ghostscript" : null;
      phase = { kind: "error", message, retry: () => run(label, job), install };
      State.stateOverride = null;
    }
    State.notify();
  }

  // ── What each bubble does ──

  function convertTo(t: { ext: string; label: string }) {
    void run(`Turning it into ${t.label}…`, async () => ({ path: await Bridge.convertFile(source, t.ext) }));
  }

  function act(action: string) {
    switch (action) {
      case "summary":
        void run("Reading it…", async () => ({ title: "In short", text: await Bridge.summarizeFile(source) }));
        break;
      case "text":
        void run("Reading the text…", async () => ({ title: "Text in the picture", text: await Bridge.ocrImage(source) }));
        break;
      case "compress":
        void run("Making it smaller…", async () => ({ path: await Bridge.compressPdf(source) }));
        break;
      case "merge": {
        const list = pdfs();
        void run(`Merging ${list.length} PDFs…`, async () => ({ path: await Bridge.mergePdfs(list) }));
        break;
      }
      case "translate":
        phase = { kind: "sub", action, title: "Translate into…", options: LANGS };
        State.notify();
        break;
      case "resize":
        phase = { kind: "sub", action, title: "Resize to…", options: SIZES };
        State.notify();
        break;
      case "ask":
        actions.setView("prompt");
        break;
      case "show":
        void Bridge.openFile(source, true);
        break;
      case "more":
        State.promptDraft = `${State.snipMode ? "About this screenshot: " : `For ${source}: `}`;
        actions.setView("prompt");
        break;
    }
  }

  function sub(action: string, o: Option) {
    if (action === "translate") {
      // Pictures: read the text, then translate it. Files: a translated copy.
      if (IMAGES.includes(ext(source))) {
        void run(`Translating into ${o.label}…`, async () => {
          const text = await Bridge.ocrImage(source);
          return { title: `In ${o.label}`, text: await Bridge.translateText(text, o.key) };
        });
      } else {
        void run(`Translating into ${o.label}…`, async () => ({ path: await Bridge.translateFile(source, o.key) }));
      }
    } else if (action === "resize") {
      void run(`Resizing to ${o.icon} px…`, async () => ({ path: await Bridge.resizeImage(source, Number(o.key)) }));
    }
  }

  /** The actions that make sense for this file. */
  function actionsFor(): Option[] {
    const e = ext(source);
    const list: Option[] = [];
    if (State.snipMode) {
      list.push({ key: "ask", label: "Ask", icon: "💬" }, { key: "text", label: "Copy text", icon: "🔤" });
      list.push({ key: "translate", label: "Translate", icon: "🌐" }, { key: "show", label: "Show", icon: "📁" });
      return list;
    }
    list.push({ key: "ask", label: "Ask", icon: "💬" });
    if (pdfs().length >= 2) list.push({ key: "merge", label: `Merge ${pdfs().length}`, icon: "📎" });
    if (READABLE.includes(e) && !IMAGES.includes(e)) list.push({ key: "summary", label: "Summary", icon: "📝" });
    if (READABLE.includes(e)) list.push({ key: "translate", label: "Translate", icon: "🌐" });
    if (IMAGES.includes(e)) list.push({ key: "text", label: "Copy text", icon: "🔤" }, { key: "resize", label: "Resize", icon: "📐" });
    if (e === "pdf") list.push({ key: "compress", label: "Compress", icon: "🗜️" });
    return list;
  }

  function pill(text: string, onClick: () => void, primary = false): HTMLElement {
    return h("button", { class: primary ? "btn primary" : "cv-chip", text, onclick: onClick });
  }

  function bubble(key: string, big: string, small: string, onPick: () => void): HTMLElement {
    const inner = h("span", { class: "cv-bubble-in" }, h("b", { text: big }), h("small", { text: small }));
    const b = h("button", { class: "cv-bubble", title: small }, inner);
    b.style.setProperty("--tint", TINT[key] ?? TINT.more);
    b.addEventListener("click", () => swallow(b, onPick));
    return b;
  }

  /** Bubbles in a gentle arc, each floating on its own beat. */
  function row(bubbles: HTMLElement[], cls = "cv-row-b"): HTMLElement {
    const r = h("div", { class: cls });
    bubbles.forEach((b, i) => {
      const n = bubbles.length;
      const lift = n > 1 ? Math.sin((i / (n - 1)) * Math.PI) * 8 : 0;
      b.style.marginTop = `${10 - lift}px`;
      (b.firstChild as HTMLElement).style.animationDelay = `${(i * 0.37) % 2}s`;
      r.append(b);
    });
    return r;
  }

  function draw() {
    clear(stage);
    stage.className = "cv-stage";
    switch (phase.kind) {
      case "pick": {
        const tools = actionsFor().map((a) => bubble(a.key, a.icon ?? "", a.label, () => act(a.key)));
        const formats = State.snipMode ? [] : targets.map((t) => bubble(t.ext, t.ext.toUpperCase(), t.label, () => convertTo(t)));
        const more = bubble("more", "…", "Other", () => act("more"));
        title.textContent = State.snipMode ? "Your screenshot — what now?" : `Do something with ${fileName()}`;
        foot.textContent = State.snipMode ? "Saved in Putshi's snips for now." : "New files go next to the original.";
        if (formats.length) {
          stage.append(row([...formats, ...(tools.length ? [] : [more])]));
          if (tools.length) stage.append(row([...tools, more], "cv-row-b tools"));
        } else {
          stage.append(row([...tools, more]));
        }
        burst([...stage.querySelectorAll<HTMLElement>(".cv-bubble")]);
        break;
      }
      case "sub": {
        const p = phase;
        title.textContent = p.title;
        foot.textContent = p.action === "translate" && !IMAGES.includes(ext(source))
          ? "A translated copy is saved next to the original."
          : "";
        const bubbles = p.options.map((o) => bubble(p.action, o.icon ?? o.label, o.label, () => sub(p.action, o)));
        bubbles.push(bubble("more", "←", "Back", () => {
          phase = { kind: "pick" };
          State.notify();
        }));
        stage.append(row(bubbles));
        burst(bubbles);
        break;
      }
      case "working":
        title.textContent = phase.label;
        foot.textContent = "Big files can take a minute.";
        stage.classList.add("working");
        stage.append(h("div", { class: "cv-progress" }, h("i")));
        break;
      case "done": {
        const out = phase.path;
        const newName = nameOf(out);
        title.textContent = "Done";
        foot.textContent = out.replace(/[\\/][^\\/]+$/, "");
        const result = h("div", { class: "cv-result" }, h("span", { class: "cv-check", text: "✓" }), h("span", { text: newName }));
        result.style.setProperty("--tint", TINT[ext(newName)] ?? TINT.more);
        const buttons = h(
          "div",
          { class: "cv-actions" },
          pill("Open", () => void Bridge.openFile(out), true),
          pill("Show in folder", () => void Bridge.openFile(out, true)),
          pill("Something else", () => {
            phase = { kind: "pick" };
            State.notify();
          }),
        );
        stage.append(result, buttons);
        burst([result]);
        break;
      }
      case "text": {
        const p = phase;
        title.textContent = p.title;
        foot.textContent = "";
        const box = h("div", { class: "cv-text", text: p.text });
        const copy = pill("Copy", () => {
          void Bridge.copyText(p.text).then(() => {
            copy.textContent = "Copied ✓";
          });
        }, true);
        const buttons = h(
          "div",
          { class: "cv-actions" },
          copy,
          pill("Ask more", () => actions.setView("prompt")),
          pill("Something else", () => {
            phase = { kind: "pick" };
            State.notify();
          }),
        );
        stage.append(box, buttons);
        burst([box]);
        break;
      }
      case "error": {
        const p = phase;
        const buttons = h("div", { class: "cv-actions show" });
        if (p.install) {
          const what = p.install;
          title.textContent = what === "ffmpeg" ? "Audio and video need ffmpeg" : "Compressing needs Ghostscript";
          foot.textContent = "A free tool, installed once with Windows' own installer (about a minute).";
          buttons.append(
            pill(`Install ${what === "ffmpeg" ? "ffmpeg" : "Ghostscript"}`, async () => {
              phase = { kind: "working", label: `Installing ${what}…` };
              State.notify();
              try {
                await (what === "ffmpeg" ? Bridge.installFfmpeg() : Bridge.installGhostscript());
                await p.retry?.();
              } catch (err) {
                phase = { kind: "error", message: errText(err), retry: null, install: null };
                State.notify();
              }
            }, true),
            pill("Cancel", () => actions.collapse()),
          );
        } else {
          title.textContent = "That didn't work";
          foot.textContent = "";
          stage.append(h("div", { class: "cv-text dim", text: p.message }));
          buttons.append(
            pill("Ask Putshi to do it", () => act("more"), true),
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
        if (!State.snipMode) {
          void Bridge.convertTargets(src).then((list) => {
            targets = list ?? [];
            drawn = "";
            State.notify();
          });
        }
      }
      // Redraw (and replay the burst) only when something actually changed,
      // and only while the card is on screen so the burst is seen.
      const key = JSON.stringify([phase.kind, "title" in phase ? phase.title : "", "label" in phase ? phase.label : "",
        "path" in phase ? phase.path : "", "message" in phase ? phase.message : "", targets.length,
        State.droppedAll.length, State.snipMode, State.view === "convert"]);
      if (key === drawn || State.view !== "convert") return;
      drawn = key;
      draw();
    },
  };
}
