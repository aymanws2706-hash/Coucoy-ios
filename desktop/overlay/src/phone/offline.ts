// Offline mode for the phone page: when the PC can't be reached, the phone
// talks to Claude itself (with the key the PC handed over while paired) and
// anything that needs the PC becomes a signed task the PC runs when it's on.

export interface OfflineConfig {
  apiKey: string | null;
  model: string;
  memory: string[];
  jobsTopic: string | null;
  /** The user's ntfy topic, for reminders the phone sets itself. */
  alertsTopic?: string | null;
  host: string;
}

export interface PhoneJob {
  id: string;
  instruction: string;
  runAt: number | null;
  sig: string;
  created: number;
  /** Handed to the PC through the phone link. */
  delivered: boolean;
  /** Left on the ntfy topic for the PC to pick up. */
  posted: boolean;
  status?: string;
  result?: string;
}

const CONFIG_KEY = "putshi.offline";
const JOBS_KEY = "putshi.jobs";

function read<T>(key: string, fallback: T): T {
  try {
    const v = localStorage.getItem(key);
    return v ? (JSON.parse(v) as T) : fallback;
  } catch {
    return fallback;
  }
}

function write(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage full or blocked */
  }
}

export const loadConfig = () => read<OfflineConfig | null>(CONFIG_KEY, null);
export const saveConfig = (c: OfflineConfig) => write(CONFIG_KEY, c);
export const loadJobs = () => read<PhoneJob[]>(JOBS_KEY, []);
export const saveJobs = (jobs: PhoneJob[]) => write(JOBS_KEY, jobs.slice(-40));

// ── Signing ───────────────────────────────────────────────────────────────────

/** HMAC-SHA256 over "id\ninstruction\nrunAt" with the pairing token (same as jobs.rs). */
async function sign(token: string, id: string, instruction: string, runAt: number | null): Promise<string> {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey("raw", enc.encode(token), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const mac = await crypto.subtle.sign("HMAC", key, enc.encode(`${id}\n${instruction}\n${runAt ?? ""}`));
  return [...new Uint8Array(mac)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

/** Creates a task and leaves it on ntfy when there's a topic. */
export async function queueJob(token: string, instruction: string, runAt: number | null): Promise<PhoneJob> {
  const id = `job-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
  const job: PhoneJob = {
    id, instruction, runAt, sig: await sign(token, id, instruction, runAt),
    created: Date.now(), delivered: false, posted: false, status: "waiting for the PC",
  };
  const topic = loadConfig()?.jobsTopic;
  if (topic) {
    try {
      const res = await fetch("https://ntfy.sh/", {
        method: "POST",
        body: JSON.stringify({ topic, message: JSON.stringify({ id, instruction, runAt, sig: job.sig }) }),
      });
      job.posted = res.ok;
    } catch {
      /* no signal: it goes through the phone link next time */
    }
  }
  saveJobs([...loadJobs(), job]);
  return job;
}

// ── Talking to Claude directly ────────────────────────────────────────────────

interface Block {
  type: string;
  text?: string;
  id?: string;
  name?: string;
  input?: Record<string, unknown>;
}

const SCHEDULE_TOOL = {
  name: "schedule_for_pc",
  description:
    "Leave a task for the user's Windows PC, which is off or unreachable right now. The PC's own assistant (with file, app, " +
    "PowerShell, music and timer tools, asking the user before risky actions) will do it as soon as the PC is on, or at `when`. " +
    "Write the instruction clearly and completely, as if for someone who can't ask you questions.",
  input_schema: {
    type: "object",
    properties: {
      instruction: { type: "string", description: "What to do on the PC." },
      when: { type: "string", description: "Optional local date-time to do it, like 2026-10-16T09:00. Leave out for 'as soon as the PC is on'." },
    },
    required: ["instruction"],
  },
};

const REMIND_TOOL = {
  name: "remind_me",
  description:
    "Remind the user at a time (call someone back, text someone…). It arrives as a phone alert at that time, up to 3 days ahead.",
  input_schema: {
    type: "object",
    properties: {
      what: { type: "string", description: "The reminder, written to the user." },
      when: { type: "string", description: "Local date-time, like 2026-10-16T18:30." },
    },
    required: ["what", "when"],
  },
};

async function remind(what: string, when: string): Promise<string> {
  const topic = loadConfig()?.alertsTopic;
  if (!topic) return "No alerts topic set (Putshi › Settings › Phone › ntfy topic on the PC), so I can't send reminders yet.";
  const at = new Date(when).getTime();
  if (Number.isNaN(at)) return "I couldn't read that time.";
  const res = await fetch("https://ntfy.sh/", {
    method: "POST",
    body: JSON.stringify({ topic, title: "⏰ Reminder", message: what, tags: ["alarm_clock"], delay: String(Math.round(at / 1000)) }),
  });
  return res.ok ? `Reminder set for ${new Date(at).toLocaleString()}.` : `ntfy refused it (${res.status}).`;
}

function systemPrompt(cfg: OfflineConfig): string {
  const now = new Date();
  const lines = [
    "You are Putshi, the user's personal assistant, shaped like a little drop of liquid glass. You're on their iPhone.",
    `The user's Windows PC${cfg.host ? ` (${cfg.host})` : ""} is OFF or unreachable right now, so you can't touch it directly.`,
    "You can chat, think things through, search the web, set reminders with remind_me, and use schedule_for_pc to leave tasks the PC will do when it's back on (optionally at a set time).",
    "Before scheduling, make sure you understand what the user wants; then confirm what you queued and when it will run.",
    `Now: ${now.toLocaleString()} (the phone's local time; the PC uses the same).`,
    "Reply in the user's language. Keep answers short. No markdown.",
  ];
  if (cfg.memory.length) lines.push("What you remember about the user:\n" + cfg.memory.map((m, i) => `${i + 1}. ${m}`).join("\n"));
  return lines.join("\n");
}

export interface DirectMsg {
  role: "user" | "assistant";
  content: string | Block[] | Record<string, unknown>[];
}

/**
 * One turn with Claude from the phone. `history` is the API-format
 * conversation (kept by the caller); returns the reply text.
 */
export async function directChat(
  token: string,
  history: DirectMsg[],
  text: string,
  onQueued: (job: PhoneJob) => void,
): Promise<string> {
  const cfg = loadConfig();
  if (!cfg?.apiKey) throw new Error("Open Putshi once while the PC is on, so the phone can learn how to reach Claude.");
  const start = history.length;
  history.push({ role: "user", content: text });
  let reply = "";
  try {
    for (let round = 0; round < 8; round++) {
      const res = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: {
          "x-api-key": cfg.apiKey,
          "anthropic-version": "2023-06-01",
          "anthropic-dangerous-direct-browser-access": "true",
          "content-type": "application/json",
        },
        body: JSON.stringify({
          model: cfg.model,
          max_tokens: 2048,
          system: systemPrompt(cfg),
          tools: [SCHEDULE_TOOL, REMIND_TOOL, { type: "web_search_20260209", name: "web_search", max_uses: 3 }],
          messages: history,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(`Claude ${res.status}: ${data?.error?.message ?? "request failed"}`);
      if (data.stop_reason === "refusal") throw new Error("Claude declined this one.");
      const blocks: Block[] = data.content ?? [];
      history.push({ role: "assistant", content: blocks });
      const t = blocks.filter((b) => b.type === "text").map((b) => b.text).join("\n").trim();
      if (t) reply = t;
      if (data.stop_reason === "pause_turn") continue;
      if (data.stop_reason !== "tool_use") break;
      const results = [];
      for (const b of blocks) {
        if (b.type === "tool_use" && b.name === "remind_me") {
          const out = await remind(String(b.input?.what ?? ""), String(b.input?.when ?? "")).catch((e) => String(e));
          results.push({ type: "tool_result", tool_use_id: b.id, content: out });
          continue;
        }
        if (b.type !== "tool_use" || b.name !== "schedule_for_pc") continue;
        const instruction = String(b.input?.instruction ?? "").trim();
        const when = b.input?.when ? new Date(String(b.input.when)).getTime() : null;
        if (!instruction) {
          results.push({ type: "tool_result", tool_use_id: b.id, content: "Empty instruction.", is_error: true });
          continue;
        }
        const job = await queueJob(token, instruction, when && !Number.isNaN(when) ? when : null);
        onQueued(job);
        const whenText = job.runAt ? new Date(job.runAt).toLocaleString() : "as soon as the PC is on";
        results.push({
          type: "tool_result",
          tool_use_id: b.id,
          content: `Queued (${job.posted ? "sent to the PC's mailbox" : "kept on the phone until it reconnects"}). It will run ${whenText}.`,
        });
      }
      history.push({ role: "user", content: results });
    }
  } catch (err) {
    history.splice(start);
    throw err;
  }
  return reply || "Done.";
}
