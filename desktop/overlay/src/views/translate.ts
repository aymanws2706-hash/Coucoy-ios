// Personal build: Ctrl+Alt+T — the text selected in any app, translated.
// The language chips switch the target; the last one picked is remembered.

import { h, clear } from "./dom";
import { Bridge } from "../core/bridge";
import { State } from "../core/state";
import type { ViewActions, ViewHost } from "./views";

const LANGS: [string, string][] = [
  ["English", "EN"],
  ["French", "FR"],
  ["Arabic", "AR"],
  ["Spanish", "ES"],
];

function savedLang(): string {
  try {
    return localStorage.getItem("putshi.lang") ?? "English";
  } catch {
    return "English";
  }
}

export function buildTranslate(actions: ViewActions): ViewHost {
  const original = h("div", { class: "tr-orig" });
  const result = h("div", { class: "cv-text tr-result" });
  const chips = h("div", { class: "tr-chips" });
  const copy = h("button", { class: "btn primary", text: "Copy" });
  const el = h(
    "div",
    { class: "view" },
    h("div", { class: "card" }, h("div", { class: "cv-wrap" }, original, result, h("div", { class: "cv-actions show" }, copy, chips))),
  );

  let lang = savedLang();
  let source = "";
  let translated = "";
  let busy = false;
  let token = 0;

  async function go() {
    const mine = ++token;
    busy = true;
    translated = "";
    State.stateOverride = "thinking";
    State.notify();
    try {
      const text = await Bridge.translateText(source, lang);
      if (mine !== token) return;
      translated = text;
    } catch (err) {
      if (mine !== token) return;
      translated = String(err).replace(/^Error:\s*/, "");
    }
    busy = false;
    State.stateOverride = null;
    State.notify();
  }

  copy.addEventListener("click", () => {
    if (!translated) return;
    void Bridge.copyText(translated).then(() => {
      copy.textContent = "Copied ✓";
      window.setTimeout(() => (copy.textContent = "Copy"), 1500);
    });
  });

  return {
    el,
    sync() {
      if (State.view !== "translate") return;
      if (State.translateSource !== source) {
        source = State.translateSource;
        if (source.trim()) void go();
      }
      original.textContent = source.trim() ? source : "Select some text in any app, then press Ctrl+Alt+T.";
      result.textContent = !source.trim() ? "" : busy ? "Translating…" : translated;
      result.classList.toggle("dim", busy);
      clear(chips);
      for (const [name, code] of LANGS) {
        const b = h("button", { class: name === lang ? "cv-chip on" : "cv-chip", text: code, title: name });
        b.addEventListener("click", () => {
          actions.blip();
          lang = name;
          try {
            localStorage.setItem("putshi.lang", name);
          } catch {
            /* remembered until restart */
          }
          if (source.trim()) void go();
          else State.notify();
        });
        chips.append(b);
      }
    },
  };
}
