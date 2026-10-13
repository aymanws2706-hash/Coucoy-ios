// Chat view — DOM port of PromptView / ChatBubble / TypingDotsView from
// IslandViewContent.swift.

import { h, svg, clear } from "./dom";
import { ICONS } from "./icons";
import { Bridge, type ChatContext } from "../core/bridge";
import { Sound } from "../core/sound";
import { State, type ChatMessage } from "../core/state";
import type { ViewHost } from "./views";

let nextId = 1;

function bubble(message: ChatMessage): HTMLElement {
  if (message.role === "user") {
    return h(
      "div",
      { class: "chat-row user" },
      h("div", { class: "bubble", text: message.content }),
    );
  }
  return h("div", { class: "chat-row" }, h("div", { class: "reply", text: message.content }));
}

function typingDots(step: string | null): HTMLElement {
  return h(
    "div",
    { class: "chat-row thinking" },
    h("div", { class: "typing" }, h("i"), h("i"), h("i")),
    step ? h("div", { class: "chat-step", text: step }) : null,
  );
}

// ── Personal build: replies read aloud ─────────────────────────────────────

const SPEAK_KEY = "mochi.speak";

function speakEnabled(): boolean {
  try {
    return localStorage.getItem(SPEAK_KEY) === "1";
  } catch {
    return false;
  }
}

function setSpeakEnabled(on: boolean) {
  try {
    localStorage.setItem(SPEAK_KEY, on ? "1" : "0");
  } catch {
    /* private storage unavailable: the toggle just won't stick */
  }
  if (!on) window.speechSynthesis?.cancel();
}

/** Reads a reply with the Windows voices, in the reply's language when it can tell. */
function speak(text: string) {
  const synth = window.speechSynthesis;
  if (!synth) return;
  synth.cancel();
  const u = new SpeechSynthesisUtterance(text.slice(0, 1200));
  if (/[\u0600-\u06FF]/.test(text)) u.lang = "ar";
  else if (/\b(je|tu|vous|est|les|une|pour|avec|c'est)\b/i.test(text)) u.lang = "fr-FR";
  else u.lang = "en-US";
  const voice = synth.getVoices().find((v) => v.lang.toLowerCase().startsWith(u.lang.toLowerCase().slice(0, 2)));
  if (voice) u.voice = voice;
  u.rate = 1.05;
  synth.speak(u);
}

/** The coloured chip showing what the question is about (a dropped file). */
function contextChip(label: string): HTMLElement {
  const chip = h("div", { class: "chip" }, h("i", { class: "chip-dot" }), h("span", { text: label }));
  requestAnimationFrame(() => chip.classList.add("settled"));
  return chip;
}

export function buildPrompt(onHeightChange: () => void): ViewHost {
  const chipRow = h("div", { class: "chip-row" });
  const log = h("div", { class: "chat-log" });
  const input = h("input", {
    type: "text",
    class: "chat-input",
    placeholder: "Ask me anything…",
    spellcheck: "false",
  }) as HTMLInputElement;
  const send = h("button", { class: "send-btn", title: "Send" }, svg(ICONS.arrowUp, 11));
  const mic = h("button", { class: "chat-tool", title: "Talk (Windows voice typing)" }, svg(ICONS.mic, 13));
  const voice = h("button", { class: "chat-tool", title: "Read replies aloud" });
  const fresh = h("button", { class: "chat-tool", title: "New conversation" }, svg(ICONS.plus, 12));
  const bar = h("div", { class: "chat-bar" }, input, fresh, voice, mic, send);

  function syncVoice() {
    clear(voice);
    voice.append(svg(speakEnabled() ? ICONS.speakerOn : ICONS.speakerOff, 13));
    voice.classList.toggle("on", speakEnabled());
  }
  syncVoice();
  voice.addEventListener("click", () => {
    setSpeakEnabled(!speakEnabled());
    syncVoice();
    Sound.play("blip");
  });
  mic.addEventListener("click", () => {
    input.focus();
    // Give the field focus first: voice typing writes wherever the caret is.
    window.setTimeout(() => {
      Bridge.startDictation().catch((err) => {
        State.noteMessage = String(err).replace(/^Error:\s*/, "");
        State.notify();
      });
    }, 150);
  });
  fresh.addEventListener("click", () => {
    if (sending) return;
    State.chatHistory = [];
    State.droppedFile = null;
    State.promptContext = null;
    void Bridge.chatReset();
    window.speechSynthesis?.cancel();
    Sound.play("blip");
    State.notify();
    onHeightChange();
    input.focus();
  });

  const el = h(
    "div",
    { class: "view" },
    h("div", { class: "card wash chat-card" }, h("div", { class: "chat-body" }, chipRow, log, bar)),
  );
  (el.querySelector(".card") as HTMLElement).style.setProperty("--wash", "rgba(99,102,241,0.5)");

  let sending = false;
  let renderedCount = "";

  async function submit() {
    const query = input.value.trim();
    if (!query || sending) return;
    input.value = "";
    sending = true;
    Sound.play("send");

    State.chatHistory.push({ id: nextId++, role: "user", content: query });
    State.stateOverride = "thinking";
    State.notify();
    onHeightChange();

    const file = State.droppedFile;
    const context: ChatContext | null =
      State.chatHistory.length === 1 && file ? { kind: "file", name: file.name, path: file.path } : null;

    try {
      const reply = await Bridge.chatSend(query, context);
      State.chatHistory.push({ id: nextId++, role: "assistant", content: reply.text });
      State.stateOverride = null;
      Sound.play("finish");
      if (speakEnabled()) speak(reply.text);
    } catch (err) {
      State.stateOverride = null;
      State.noteMessage = String(err).replace(/^Error:\s*/, "");
      State.view = "note";
      Sound.play("error");
    } finally {
      State.chatStep = null;
      sending = false;
      State.notify();
      onHeightChange();
      input.focus();
    }
  }

  send.addEventListener("click", () => void submit());
  input.addEventListener("keydown", (e) => {
    if ((e as KeyboardEvent).key === "Enter") {
      e.preventDefault();
      void submit();
    }
    e.stopPropagation(); // Escape closes the island, not the chat
  });

  return {
    el,
    sync() {
      const file = State.droppedFile;
      const wantChip = file?.name ?? "";
      if (chipRow.dataset.label !== wantChip) {
        chipRow.dataset.label = wantChip;
        clear(chipRow);
        if (wantChip) chipRow.append(contextChip(wantChip));
      }

      const thinking = State.stateOverride === "thinking";
      const count = `${State.chatHistory.length}|${thinking}|${State.chatStep ?? ""}`;
      if (count !== renderedCount) {
        renderedCount = count;
        clear(log);
        for (const m of State.chatHistory) log.append(bubble(m));
        if (thinking) log.append(typingDots(State.chatStep));
        log.scrollTop = log.scrollHeight;
      }

      input.placeholder = State.chatHistory.length === 0 ? "Ask me anything…" : "Continue…";
      input.disabled = sending;
    },
    focus() {
      input.focus();
      input.select();
    },
  };
}
