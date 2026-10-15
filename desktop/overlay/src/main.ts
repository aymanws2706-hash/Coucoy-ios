// Entry point: boot the bridge, wire the island, start the greeting.

import "./style.css";
import { Bridge, IS_TAURI, onEvent } from "./core/bridge";
import { Sound } from "./core/sound";
import { State, type Settings } from "./core/state";
import { Island } from "./island/island";
import { registerHookHandlers } from "./island/hooks";
import { registerIntegrationHandlers, refreshConfigured } from "./island/integrations";
import "./glass.css";

async function main() {
  const root = document.getElementById("root");
  if (!root) return;

  void Sound.preload();

  const island = new Island(root);

  const boot = await Bridge.boot();
  if (boot) {
    State.settings = { ...State.settings, ...boot.settings };
  }
  island.applySettings();
  State.loadIntegrationTasks();
  if (boot && !boot.cursorPoll) island.followPageCursor();

  await onEvent<{ x: number; y: number }>("cursor", ({ x, y }) => island.onCursor(x, y));

  /** Pause has to reach Rust too, or the pollers keep calling out. */
  const setPaused = (on: boolean) => {
    if (State.paused === on) return;
    State.paused = on;
    void Bridge.setPaused(on);
  };

  await onEvent<string>("tray", (what) => {
    switch (what) {
      case "settings":
        setPaused(false);
        island.alert("settings");
        break;
      case "open":
        setPaused(false);
        island.alert(State.defaultView());
        break;
      case "pause":
        setPaused(!State.paused);
        if (State.paused) island.fsm.forceHidden();
        else island.reveal();
        break;
    }
  });

  await onEvent<null>("screen-changed", () => void Bridge.reposition());

  // The settings window writes preferences; apply them here without a restart.
  await onEvent<Settings>("settings-changed", (s) => {
    State.settings = { ...State.settings, ...s };
    island.applySettings();
    State.loadIntegrationTasks();
    void refreshConfigured();
  });

  // ── Personal build: Liquid Glass ────────────────────────────────────────
  const applyGlass = async () => {
    // The desktop blur is experimental (on some PCs Windows frosts the whole
    // window instead of the island): off unless switched on in Settings.
    let want = false;
    try {
      want = localStorage.getItem("putshi.glassblur") === "1";
    } catch {
      /* storage blocked: keep the default */
    }
    // Always tell Rust, so a blur left on by an older build is cleared.
    const took = IS_TAURI ? ((await Bridge.setGlass(want)) ?? false) : want;
    document.documentElement.classList.toggle("glass", want && took);
    document.documentElement.classList.toggle("no-glass", !(want && took));
    island.reshape();
  };
  await applyGlass();
  await onEvent<null>("glass-changed", () => void applyGlass());

  // ── Personal build: Mochi's assistant ───────────────────────────────────
  await onEvent<string>("hotkey", () => {
    setPaused(false);
    island.openChat();
  });
  await onEvent<{ minutes: number; label: string }>("timer", ({ minutes, label }) => {
    island.startTimer(minutes, label);
  });
  await onEvent<null>("timer-stop", () => island.stopTimer());
  await onEvent<"allow" | "deny">("phone-claude", (d) => island.decideFromPhone(d));
  await onEvent<string>("mochi-step", (text) => {
    State.chatStep = text;
    State.notify();
  });
  await onEvent<{ id: number; what: string; detail: string }>("mochi-approval", ({ id, what, detail }) => {
    State.pendingApproval = { requestId: `mochi:${id}`, sessionId: "", tool: what, command: detail };
    State.isPinned = true;
    Sound.play("approval");
    island.alert("approval");
  });
  // Timed out (or answered elsewhere): take the card down.
  await onEvent<number>("mochi-approval-done", (id) => {
    if (State.pendingApproval?.requestId !== `mochi:${id}`) return;
    State.pendingApproval = null;
    State.isPinned = false;
    island.dropPin();
    if (State.view === "approval") island.setView("prompt");
  });

  registerHookHandlers(island);
  registerIntegrationHandlers(island);

  island.launch();

  // In a plain browser there is no wake strip behind the cursor: make the whole
  // page wake the island so the visuals can be checked with `npm run dev`.
  if (!IS_TAURI) {
    document.addEventListener("click", () => Sound.resume(), { once: true });
  }
}

void main();
