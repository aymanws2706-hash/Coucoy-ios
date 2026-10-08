"""Putshi bridge: lets Putshi on the iPhone run jobs on this PC.

Putshi (the phone app) sends a plain-language instruction. The bridge runs it
with Claude and a small set of PC tools, reports each step back to the phone,
and pauses for the user's Allow / Deny on the phone before anything that
changes the PC (writing files, running commands, opening apps).

Run it on the PC:
    pip install -r requirements.txt
    python putshi_bridge.py --env C:\\Users\\ayman\\jarvis\\.env

Then expose it to the phone with HTTPS over Tailscale:
    tailscale serve --bg 8770

Protocol (JSON, header "Authorization: Bearer <token>"):
    GET  /putshi/ping                      -> {"ok": true, "name": "<pc name>"}
    POST /putshi/tasks {"instruction"}     -> {"id": "..."}
    GET  /putshi/tasks/<id>                -> {"id","status","steps":[{"text","status"}],"result","approval"}
    POST /putshi/tasks/<id>/approval {"allow": true|false}

status: queued | running | needs_approval | done | failed

To hand jobs to JARVIS's own brain instead of this built-in agent, replace
run_agent() with a call into JARVIS and keep the Task step / approval calls.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import secrets
import subprocess
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import anthropic

MODEL = "claude-opus-5-5"
TOKEN_FILE = Path.home() / ".putshi_bridge_token"
HOME = Path.home()
APPROVAL_TIMEOUT_S = 10 * 60
MAX_READ_CHARS = 20_000

SYSTEM_PROMPT = f"""You are the PC side of Putshi, a personal assistant. Instructions come from Putshi on the \
user's iPhone; the user is not at this computer. You run on {platform.system()} ({platform.node()}), \
user home {HOME}.

Work out the steps, then use the tools to do them. Read before you change anything. Keep each tool call \
focused. Writing files, running commands and opening apps each ask the user on their phone first; if they \
deny, don't retry the same action - explain what you'd need instead.

End with a short plain-text result for the phone: what you did, where outputs are, and anything the user \
must do themselves. Never claim an action succeeded unless the tool result says so."""


# --------------------------------------------------------------------------- tasks

class Task:
    def __init__(self, instruction: str):
        self.id = uuid.uuid4().hex[:12]
        self.instruction = instruction
        self.status = "queued"
        self.steps: list[dict] = []
        self.result: str | None = None
        self.approval: dict | None = None
        self._lock = threading.Lock()
        self._answer = threading.Event()
        self._allowed = False

    def to_json(self) -> dict:
        with self._lock:
            return {
                "id": self.id,
                "status": self.status,
                "steps": [dict(s) for s in self.steps],
                "result": self.result,
                "approval": self.approval,
            }

    def step(self, text: str) -> int:
        with self._lock:
            self.steps.append({"text": text[:80], "status": "running"})
            return len(self.steps) - 1

    def end_step(self, i: int, ok: bool) -> None:
        with self._lock:
            self.steps[i]["status"] = "done" if ok else "failed"

    def ask(self, question: str) -> bool:
        """Blocks until the user answers on the phone (or the wait times out)."""
        with self._lock:
            self.approval = {"question": question}
            self.status = "needs_approval"
            self._answer.clear()
        answered = self._answer.wait(APPROVAL_TIMEOUT_S)
        with self._lock:
            self.approval = None
            self.status = "running"
            return answered and self._allowed

    def answer(self, allow: bool) -> None:
        with self._lock:
            self._allowed = allow
        self._answer.set()

    def finish(self, ok: bool, result: str) -> None:
        with self._lock:
            self.status = "done" if ok else "failed"
            self.result = result


TASKS: dict[str, Task] = {}


# --------------------------------------------------------------------------- PC tools

def _strict(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "name": name,
        "description": description,
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
    }


TOOLS = [
    _strict("list_directory", "List files and folders in a directory (name, size, modified date).",
            {"path": {"type": "string"}}, ["path"]),
    _strict("find_files", "Find files under a folder whose name matches a glob pattern such as *.rvt.",
            {"root": {"type": "string"}, "pattern": {"type": "string"}}, ["root", "pattern"]),
    _strict("read_text_file", "Read a text file (first 20,000 characters).",
            {"path": {"type": "string"}}, ["path"]),
    _strict("write_text_file", "Create or overwrite a text file. Asks the user on their phone first.",
            {"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"]),
    _strict("open_path", "Open a file, folder or app with its default program. Asks the user first.",
            {"path": {"type": "string"}}, ["path"]),
    _strict("run_command", "Run a PowerShell command (bash on non-Windows) and return its output. Asks the user first.",
            {"command": {"type": "string"}, "why": {"type": "string", "description": "One line the user sees when approving."}},
            ["command", "why"]),
]


def _resolve(p: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(p))).resolve()


def run_tool(task: Task, name: str, args: dict) -> tuple[str, bool]:
    """Returns (output, ok). Each call shows up as a step on the phone."""
    if name == "list_directory":
        path = _resolve(args["path"])
        i = task.step(f"Looking in {path.name or path}")
        try:
            rows = []
            for entry in sorted(path.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))[:300]:
                st = entry.stat()
                kind = "dir " if entry.is_dir() else f"{st.st_size:>10}"
                rows.append(f"{kind}  {entry.name}")
            task.end_step(i, True)
            return "\n".join(rows) or "(empty)", True
        except OSError as e:
            task.end_step(i, False)
            return f"Error: {e}", False

    if name == "find_files":
        root = _resolve(args["root"])
        i = task.step(f"Searching {root.name or root} for {args['pattern']}")
        try:
            hits = []
            for p in root.rglob(args["pattern"]):
                hits.append(str(p))
                if len(hits) >= 200:
                    break
            task.end_step(i, True)
            return "\n".join(hits) or "No matches.", True
        except OSError as e:
            task.end_step(i, False)
            return f"Error: {e}", False

    if name == "read_text_file":
        path = _resolve(args["path"])
        i = task.step(f"Reading {path.name}")
        try:
            text = path.read_text(encoding="utf-8", errors="replace")[:MAX_READ_CHARS]
            task.end_step(i, True)
            return text, True
        except OSError as e:
            task.end_step(i, False)
            return f"Error: {e}", False

    if name == "write_text_file":
        path = _resolve(args["path"])
        i = task.step(f"Writing {path.name}")
        if not task.ask(f"Write {len(args['content'])} characters to {path}?"):
            task.end_step(i, False)
            return "The user denied writing this file.", False
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(args["content"], encoding="utf-8")
            task.end_step(i, True)
            return f"Wrote {path}", True
        except OSError as e:
            task.end_step(i, False)
            return f"Error: {e}", False

    if name == "open_path":
        target = args["path"]
        i = task.step(f"Opening {Path(target).name or target}")
        if not task.ask(f"Open {target} on your PC?"):
            task.end_step(i, False)
            return "The user denied opening it.", False
        try:
            if platform.system() == "Windows":
                os.startfile(target)  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", target])
            task.end_step(i, True)
            return f"Opened {target}", True
        except OSError as e:
            task.end_step(i, False)
            return f"Error: {e}", False

    if name == "run_command":
        cmd = args["command"]
        i = task.step(args.get("why") or "Running a command")
        if not task.ask(f"{args.get('why', 'Run a command')}\n\n{cmd}"):
            task.end_step(i, False)
            return "The user denied running this command.", False
        shell = (["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd]
                 if platform.system() == "Windows" else ["bash", "-lc", cmd])
        try:
            done = subprocess.run(shell, capture_output=True, text=True, timeout=180)
            out = (done.stdout + ("\n" + done.stderr if done.stderr else ""))[-MAX_READ_CHARS:]
            ok = done.returncode == 0
            task.end_step(i, ok)
            return f"exit code {done.returncode}\n{out}", ok
        except subprocess.TimeoutExpired:
            task.end_step(i, False)
            return "The command took longer than 3 minutes and was stopped.", False

    return f"Unknown tool {name}", False


# --------------------------------------------------------------------------- agent

def _create(client: anthropic.Anthropic, messages: list) -> object:
    params = dict(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        tools=TOOLS,
        messages=messages,
        output_config={"effort": "medium"},
        betas=["server-side-fallback-2026-07-01"],
    )
    try:
        return client.beta.messages.create(fallbacks="default", **params)
    except TypeError:  # older SDK without the fallbacks keyword
        return client.beta.messages.create(extra_body={"fallbacks": "default"}, **params)


def run_agent(task: Task, client: anthropic.Anthropic) -> None:
    task.status = "running"
    messages: list = [{"role": "user", "content": task.instruction}]
    try:
        for _ in range(40):
            response = _create(client, messages)
            if response.stop_reason == "refusal":
                task.finish(False, "Claude declined this request.")
                return
            messages.append({"role": "assistant", "content": response.content})

            tool_uses = [b for b in response.content if b.type == "tool_use"]
            if response.stop_reason == "tool_use" and tool_uses:
                results = []
                for block in tool_uses:
                    output, ok = run_tool(task, block.name, block.input)
                    result = {"type": "tool_result", "tool_use_id": block.id, "content": output}
                    if not ok:
                        result["is_error"] = True
                    results.append(result)
                messages.append({"role": "user", "content": results})
                continue

            text = "\n".join(b.text for b in response.content if b.type == "text").strip()
            task.finish(True, text or "Done.")
            return
        task.finish(False, "Stopped after 40 steps without finishing.")
    except anthropic.AuthenticationError:
        task.finish(False, "The PC's Anthropic API key was rejected.")
    except anthropic.RateLimitError:
        task.finish(False, "Claude is rate limited on the PC. Try again in a minute.")
    except anthropic.APIStatusError as e:
        task.finish(False, f"Claude API error {e.status_code}: {e.message}")
    except anthropic.APIConnectionError:
        task.finish(False, "The PC can't reach Claude. Check its internet connection.")
    except Exception as e:  # keep the bridge alive whatever happens in one task
        task.finish(False, f"Unexpected error on the PC: {e}")


# --------------------------------------------------------------------------- HTTP

def make_handler(token: str, client: anthropic.Anthropic):
    class Handler(BaseHTTPRequestHandler):
        server_version = "PutshiBridge/1.0"

        def _send(self, code: int, body: dict) -> None:
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _authorized(self) -> bool:
            sent = self.headers.get("Authorization", "")
            if secrets.compare_digest(sent, f"Bearer {token}"):
                return True
            self._send(401, {"error": "bad token"})
            return False

        def _json_body(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > 1_000_000:
                return {}
            try:
                return json.loads(self.rfile.read(length))
            except json.JSONDecodeError:
                return {}

        def do_GET(self):  # noqa: N802
            if not self._authorized():
                return
            parts = self.path.strip("/").split("/")
            if parts == ["putshi", "ping"]:
                return self._send(200, {"ok": True, "name": platform.node()})
            if len(parts) == 3 and parts[:2] == ["putshi", "tasks"] and parts[2] in TASKS:
                return self._send(200, TASKS[parts[2]].to_json())
            self._send(404, {"error": "not found"})

        def do_POST(self):  # noqa: N802
            if not self._authorized():
                return
            parts = self.path.strip("/").split("/")
            body = self._json_body()
            if parts == ["putshi", "tasks"]:
                instruction = str(body.get("instruction", "")).strip()
                if not instruction:
                    return self._send(400, {"error": "instruction is required"})
                task = Task(instruction)
                TASKS[task.id] = task
                threading.Thread(target=run_agent, args=(task, client), daemon=True).start()
                print(f"[putshi] task {task.id}: {instruction[:100]}")
                return self._send(200, {"id": task.id})
            if len(parts) == 4 and parts[:2] == ["putshi", "tasks"] and parts[3] == "approval" and parts[2] in TASKS:
                TASKS[parts[2]].answer(bool(body.get("allow")))
                return self._send(200, {"ok": True})
            self._send(404, {"error": "not found"})

        def log_message(self, fmt, *args):  # quieter console
            pass

    return Handler


def load_env_file(path: str) -> None:
    """Reads KEY=VALUE lines (like JARVIS's .env) into the environment."""
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Putshi bridge")
    parser.add_argument("--port", type=int, default=8770)
    parser.add_argument("--host", default="127.0.0.1",
                        help="127.0.0.1 with 'tailscale serve' (recommended), 0.0.0.0 for the local network")
    parser.add_argument("--env", help="path to a .env file with ANTHROPIC_API_KEY (e.g. JARVIS's)")
    args = parser.parse_args()

    if args.env:
        load_env_file(args.env)

    token = os.environ.get("PUTSHI_TOKEN") or (TOKEN_FILE.read_text().strip() if TOKEN_FILE.exists() else "")
    if not token:
        token = secrets.token_urlsafe(24)
        TOKEN_FILE.write_text(token)

    client = anthropic.Anthropic()  # ANTHROPIC_API_KEY from the environment / .env
    server = ThreadingHTTPServer((args.host, args.port), make_handler(token, client))
    print(f"Putshi bridge on http://{args.host}:{args.port}")
    print(f"Token for Putshi's Settings: {token}")
    print("Expose it to your phone over HTTPS with:  tailscale serve --bg", args.port)
    server.serve_forever()


if __name__ == "__main__":
    main()
