// Thin wrapper over the Tauri commands/events. Every call is a no-op when the
// page is opened in a plain browser, so the island can be iterated on with
// `npm run dev` alone.

import { invoke } from "@tauri-apps/api/core";
import { emit, listen } from "@tauri-apps/api/event";
import { getCurrentWebview } from "@tauri-apps/api/webview";
import type { Settings } from "./state";

export const IS_TAURI =
  typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;

async function call<T>(cmd: string, args?: Record<string, unknown>): Promise<T | null> {
  if (!IS_TAURI) return null;
  try {
    return await invoke<T>(cmd, args);
  } catch (err) {
    console.error(`[coucou] ${cmd} failed`, err);
    return null;
  }
}

export interface BootInfo {
  settings: Settings;
  /** Logical screen rect of the monitor the island lives on. */
  screen: { x: number; y: number; width: number; height: number; scale: number };
  version: string;
  hookPath: string;
  /** False where the OS has no global cursor (Wayland): see Island.followPageCursor. */
  cursorPoll: boolean;
}

export const Bridge = {
  boot: () => call<BootInfo>("boot"),

  saveSettings: (settings: Settings) => call<void>("save_settings", { settings }),

  /** Shrink the window down to the invisible wake strip (hidden) or back to full. */
  setCollapsed: (collapsed: boolean) => call<void>("set_collapsed", { collapsed }),

  /**
   * Pushes the island shape in window coordinates. Rust flips click-through from
   * its own cursor poll, so the flag is never a frame behind a click.
   */
  setIslandRect: (x: number, y: number, width: number, height: number, radius = 14) =>
    call<void>("set_island_rect", { x, y, width, height, radius }),
  /** Liquid Glass blur behind the island; false when Windows refused it. */
  setGlass: (on: boolean) => call<boolean>("set_glass", { on }),

  /** Give the window keyboard focus (chat field) and take it away again. */
  focusWindow: (focused: boolean) => call<void>("focus_window", { focused }),

  reposition: () => call<void>("reposition"),

  openUrl: (url: string) => call<void>("open_url", { url }),

  /** "Open terminal" → opens the folder in VS Code when `code` is on PATH. */
  openInVSCode: (path: string | null) => call<boolean>("open_in_vscode", { path }),

  quit: () => call<void>("quit_app"),

  openSettingsWindow: () => call<void>("open_settings_window"),

  /** Writes to %LOCALAPPDATA%\Coucou\coucou.log, next to the Rust lines. */
  log: (message: string) => call<void>("log_line", { message }),

  // ── Claude Code hooks ─────────────────────────────────────────────────────
  hooksStatus: () => call<HookStatus>("hooks_status"),
  /** Diff to show before anything is written. `install: false` previews removal. */
  hooksPreview: (install: boolean) => callOrThrow<HookPreview>("hooks_preview", { install }),
  /**
   * Writes ~/.claude/settings.json — only ever after an explicit click, and only
   * when the file still matches the preview the user looked at.
   */
  hooksApply: (install: boolean, fingerprint: string) =>
    callOrThrow<string>("hooks_apply", { install, fingerprint }),

  approvalDecision: (requestId: string, decision: "allow" | "deny") =>
    call<void>("approval_decision", { requestId, decision }),
  /** "The card is up" — until this lands the relay only waits a moment. */
  approvalAck: (requestId: string) => call<void>("approval_ack", { requestId }),
  /** "Nobody can act on this" — Claude Code asks in the terminal right away. */
  approvalDecline: (requestId: string) => call<void>("approval_decline", { requestId }),

  // ── Chat, files, secrets ──────────────────────────────────────────────────
  /** One chat turn. The API key and any file bytes never leave Rust. */
  chatSend: (query: string, context: ChatContext | null) =>
    callOrThrow<{ text: string }>("chat_send", { query, context }),
  chatReset: () => call<void>("chat_reset"),
  /** Copies a dropped file into the inbox. */
  ingestFile: (path: string) => callOrThrow<DroppedFile>("ingest_file", { path }),
  /** Only ever tells you whether a key exists — never its value. */
  secretPresent: (key: string) => call<boolean>("secret_present", { key }),
  secretSet: (key: string, value: string) => callOrThrow<void>("secret_set", { key, value }),
  secretClear: (key: string) => callOrThrow<void>("secret_clear", { key }),

  // ── Integrations ──────────────────────────────────────────────────────────
  refreshIntegration: (id: string) => call<void>("refresh_integration", { id }),
  /** Opens the configured n8n instance in the browser. */
  openN8n: () => call<void>("open_n8n"),

  /** Allow / Deny on a card raised by Mochi's own chat tools. */
  mochiDecision: (id: number, allow: boolean) => call<void>("mochi_decision", { id, allow }),
  /** Presses Win+H: Windows voice typing fills the focused field. */
  startDictation: () => callOrThrow<void>("start_dictation"),
  topApps: () => call<AppUsage[]>("top_apps"),
  killApp: (name: string) => call<number>("kill_app", { name }),

  nowPlaying: () => call<NowPlaying | null>("now_playing"),
  mediaControl: (action: "toggle" | "next" | "previous") => call<void>("media_control", { action }),
  deskControls: (brightness: boolean) => call<DeskControls>("desk_controls", { brightness }),
  setVolume: (percent: number) => call<void>("set_volume", { percent }),
  setMute: (mic: boolean, muted: boolean) => call<void>("set_mute", { mic, muted }),
  setBrightness: (percent: number) => callOrThrow<void>("set_brightness", { percent }),
  deskActivity: () => call<DeskActivity>("desk_activity"),
  shortcut: (which: string) => callOrThrow<void>("shortcut", { which }),
  clipboardHistory: () => call<string[]>("clipboard_history"),
  clipboardCopy: (index: number) => call<void>("clipboard_copy", { index }),
  clipboardClear: () => call<void>("clipboard_clear"),

  weather: (force = false) => callOrThrow<Weather>("weather", { force }),
  calendar: (force = false) => callOrThrow<CalendarEvent[]>("calendar", { force }),

  phoneInfo: () => callOrThrow<PhoneInfo>("phone_info"),
  phoneEnable: () => callOrThrow<PhoneInfo>("phone_enable"),
  phoneDisable: () => callOrThrow<void>("phone_disable"),
  phonePublish: (snapshot: unknown) => call<void>("phone_publish", { snapshot }),
  /** ntfy alert; sent only when the PC has been idle 2 min unless `now`. */
  pushNotify: (title: string, message: string, now = false) =>
    call<void>("push_notify", { title, message, now }),

  awarenessGet: () => callOrThrow<AwarenessConfig>("awareness_get"),
  awarenessSet: (config: AwarenessConfig) => callOrThrow<void>("awareness_set", { config }),
  addReminder: (text: string, at: number) => call<void>("add_reminder", { text, at }),
  localTimeMs: (text: string) => call<number | null>("local_time_ms", { text }),

  /** Desktop info for the notch and the PC view. */
  systemStats: () => call<SystemStats>("system_stats"),

  /** Tray → Pause. Stops the integration pollers, not just the island. */
  setPaused: (paused: boolean) => call<void>("set_paused", { paused }),
};

export interface AwarenessConfig {
  titles: boolean;
  apps: boolean;
  screen: boolean;
  watch: string[];
  ignore: string[];
}

export interface Suggestion {
  id: string;
  text: string;
  /** Local "2026-10-16T18:30", when known. */
  when: string | null;
  why: string;
}

export interface PhoneInfo {
  enabled: boolean;
  tailscaleFound: boolean;
  url: string | null;
  qrSvg: string | null;
  message: string | null;
}

export interface NowPlaying {
  title: string;
  artist: string;
  app: string;
  playing: boolean;
  /** Seconds. */
  position: number;
  duration: number;
}

export interface DeskControls {
  volume: number | null;
  muted: boolean;
  micMuted: boolean | null;
  brightness: number | null;
  wifi: string | null;
  wifiSignal: number | null;
}

export interface DeskActivity {
  micInUse: boolean;
  cameraInUse: boolean;
  downloads: { name: string; bytes: number }[];
}

export interface Weather {
  city: string;
  temp: number;
  /** WMO weather code. */
  code: number;
  isDay: boolean;
  high: number;
  low: number;
  hours: { hour: number; temp: number; code: number; rain: number }[];
}

export interface CalendarEvent {
  title: string;
  startMs: number;
  endMs: number;
  allDay: boolean;
  location: string;
}

export interface AppUsage {
  name: string;
  /** Share of the whole CPU, 0–100. */
  cpu: number;
  memory: number;
  processes: number;
}

export interface SystemStats {
  /** 0–100, all cores. */
  cpu: number;
  memUsed: number;
  memTotal: number;
  diskUsed: number;
  diskTotal: number;
  /** Bytes per second. */
  netDown: number;
  netUp: number;
  /** null on a PC without a battery. */
  battery: number | null;
  charging: boolean;
  uptimeSecs: number;
  host: string;
}

export interface IntegrationUpdate {
  id: string;
  data: Record<string, unknown>;
  error: string | null;
  event: { success: boolean; label: string; detail: string | null } | null;
}

export type ChatContext =
  | { kind: "file"; name: string; path: string }
  | { kind: "window"; appName: string; title: string; url?: string };

export interface DroppedFile {
  name: string;
  path: string;
  size: number;
}

export interface HookStatus {
  installed: boolean;
  settingsPath: string;
  hookPath: string;
  hookReady: boolean;
}

export interface HookPreview {
  diff: string;
  backup: string;
  settingsPath: string;
  /** Hand back to hooksApply so only the reviewed diff is ever written. */
  fingerprint: string;
}

/** Same as `call`, but surfaces the error so the UI can show what went wrong. */
async function callOrThrow<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
  if (!IS_TAURI) throw new Error("not running inside Coucou");
  return invoke<T>(cmd, args);
}

export type BridgeEvent =
  | { name: "cursor"; payload: { x: number; y: number } }
  | { name: "tray"; payload: string }
  | { name: "hook"; payload: Record<string, unknown> }
  | { name: "screen-changed"; payload: null };

export interface DragDropPayload {
  type: "enter" | "over" | "drop" | "leave";
  paths?: string[];
}

/** Files dragged onto the island. Only reaches us when the window takes the mouse. */
export async function onDragDrop(handler: (e: DragDropPayload) => void) {
  if (!IS_TAURI) return () => {};
  return getCurrentWebview().onDragDropEvent((event) => {
    handler(event.payload as DragDropPayload);
  });
}

/** Tells the other window something changed (settings → island). */
export async function emitEvent(name: string) {
  if (!IS_TAURI) return;
  await emit(name);
}

export async function onEvent<T>(name: string, handler: (payload: T) => void) {
  if (!IS_TAURI) return () => {};
  return listen<T>(name, (e) => handler(e.payload));
}
