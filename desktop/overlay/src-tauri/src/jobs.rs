// Personal build: tasks for the PC, written on the phone (often while the PC
// was off). They arrive two ways — straight through the phone link when it's
// up, or through the user's private ntfy topic "<topic>-jobs" when it isn't —
// and run when they're due, with the same tools and Allow / Deny rules as a
// chat. Each one is signed with the phone's pairing token, so a stranger who
// guessed the topic name can't make the PC do anything.

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use std::time::Duration;

use hmac::{Hmac, Mac};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::Sha256;
use tauri::{AppHandle, Emitter, Manager};

use crate::{claude, phone, platform, push, secrets};

#[derive(Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct Job {
    pub id: String,
    pub instruction: String,
    /// Epoch ms; None = as soon as the PC is on.
    pub run_at: Option<i64>,
    pub created: i64,
    /// pending, running, done, failed
    pub status: String,
    pub result: String,
}

#[derive(Default)]
pub struct Jobs {
    list: Mutex<Vec<Job>>,
    loaded: AtomicBool,
    running: AtomicBool,
}

/// While a phone task runs, an approval card waits longer: the user is
/// probably away and answers from the phone.
pub static UNATTENDED: AtomicBool = AtomicBool::new(false);

fn path() -> std::path::PathBuf {
    platform::local_dir().join("jobs.json")
}

fn now_ms() -> i64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis() as i64)
        .unwrap_or(0)
}

/// HMAC-SHA256 over "id\ninstruction\nrunAt" with the pairing token, as hex.
pub fn signature(token: &str, id: &str, instruction: &str, run_at: Option<i64>) -> String {
    let mut mac = Hmac::<Sha256>::new_from_slice(token.as_bytes()).expect("any key length");
    let at = run_at.map(|v| v.to_string()).unwrap_or_default();
    mac.update(format!("{id}\n{instruction}\n{at}").as_bytes());
    mac.finalize().into_bytes().iter().map(|b| format!("{b:02x}")).collect()
}

impl Jobs {
    fn load(&self) {
        if self.loaded.swap(true, Ordering::SeqCst) {
            return;
        }
        if let Ok(bytes) = std::fs::read(path()) {
            if let Ok(list) = serde_json::from_slice::<Vec<Job>>(&bytes) {
                *self.list.lock().unwrap() = list;
            }
        }
    }

    fn save(&self) {
        let list = self.list.lock().unwrap().clone();
        let _ = platform::ensure_private_dir(&platform::local_dir());
        if let Ok(json) = serde_json::to_vec_pretty(&list) {
            let _ = std::fs::write(path(), json);
        }
    }

    pub fn list(&self) -> Vec<Job> {
        self.load();
        let mut list = self.list.lock().unwrap().clone();
        list.sort_by_key(|j| -j.created);
        list.truncate(30);
        list
    }

    /// Adds a signed task; a task already known (same id) is ignored.
    pub fn add(&self, id: &str, instruction: &str, run_at: Option<i64>, sig: &str) -> Result<bool, String> {
        self.load();
        let token = phone::token().ok_or("The phone isn't paired.")?;
        if id.is_empty() || instruction.trim().is_empty() {
            return Err("Empty task.".into());
        }
        if signature(&token, id, instruction, run_at) != sig {
            return Err("Bad signature: this task didn't come from your phone.".into());
        }
        let mut list = self.list.lock().unwrap();
        if list.iter().any(|j| j.id == id) {
            return Ok(false);
        }
        list.push(Job {
            id: id.to_string(),
            instruction: instruction.trim().to_string(),
            run_at,
            created: now_ms(),
            status: "pending".into(),
            result: String::new(),
        });
        // Keep the file small: finished tasks older than two weeks go.
        let cutoff = now_ms() - 14 * 86_400_000;
        list.retain(|j| j.status == "pending" || j.created > cutoff);
        drop(list);
        self.save();
        Ok(true)
    }

    /// A task the PC's own assistant scheduled (no phone signature needed).
    pub fn add_local(&self, instruction: &str, run_at: i64) -> Result<(), String> {
        self.load();
        if instruction.trim().is_empty() {
            return Err("Empty task.".into());
        }
        let id = format!("local-{}", now_ms());
        self.list.lock().unwrap().push(Job {
            id,
            instruction: instruction.trim().to_string(),
            run_at: Some(run_at),
            created: now_ms(),
            status: "pending".into(),
            result: String::new(),
        });
        self.save();
        Ok(())
    }

    fn set(&self, id: &str, status: &str, result: &str) {
        if let Some(j) = self.list.lock().unwrap().iter_mut().find(|j| j.id == id) {
            j.status = status.into();
            j.result = result.into();
        }
        self.save();
    }

    fn next_due(&self) -> Option<Job> {
        self.load();
        let now = now_ms();
        self.list
            .lock()
            .unwrap()
            .iter()
            .filter(|j| j.status == "pending" && j.run_at.map(|t| t <= now).unwrap_or(true))
            .min_by_key(|j| j.run_at.unwrap_or(j.created))
            .cloned()
    }
}

// ── Workers ──────────────────────────────────────────────────────────────────

/// Starts the ntfy watcher and the runner. Called once at launch.
pub fn start(app: AppHandle) {
    // Tasks that were running when the app closed run again.
    {
        let jobs = app.state::<Jobs>();
        jobs.load();
        let mut changed = false;
        for j in jobs.list.lock().unwrap().iter_mut() {
            if j.status == "running" {
                j.status = "pending".into();
                changed = true;
            }
        }
        if changed {
            jobs.save();
        }
    }

    let a = app.clone();
    tauri::async_runtime::spawn(async move {
        loop {
            fetch_from_ntfy(&a).await;
            tokio::time::sleep(Duration::from_secs(60)).await;
        }
    });

    tauri::async_runtime::spawn(async move {
        loop {
            run_due(&app).await;
            tokio::time::sleep(Duration::from_secs(20)).await;
        }
    });
}

fn since_path() -> std::path::PathBuf {
    platform::local_dir().join("jobs-since.txt")
}

/// Reads new task messages from "<ntfy-topic>-jobs" (ntfy keeps them 12 h).
async fn fetch_from_ntfy(app: &AppHandle) {
    let Some(topic) = secrets::get("ntfy-topic") else { return };
    if phone::token().is_none() {
        return;
    }
    let since = std::fs::read_to_string(since_path()).unwrap_or_else(|_| "12h".into());
    let url = format!("https://ntfy.sh/{}-jobs/json?poll=1&since={}", topic.trim(), since.trim());
    let Ok(client) = reqwest::Client::builder().timeout(Duration::from_secs(20)).build() else { return };
    let Ok(resp) = client.get(&url).send().await else { return };
    let Ok(text) = resp.text().await else { return };
    let jobs = app.state::<Jobs>();
    let mut last_id = None;
    let mut added = false;
    for line in text.lines() {
        let Ok(msg) = serde_json::from_str::<Value>(line) else { continue };
        if msg.get("event").and_then(Value::as_str) != Some("message") {
            continue;
        }
        last_id = msg.get("id").and_then(Value::as_str).map(str::to_string);
        let Some(body) = msg.get("message").and_then(Value::as_str) else { continue };
        let Ok(job) = serde_json::from_str::<Value>(body) else { continue };
        let s = |k: &str| job.get(k).and_then(Value::as_str).unwrap_or("").to_string();
        let run_at = job.get("runAt").and_then(Value::as_i64);
        match jobs.add(&s("id"), &s("instruction"), run_at, &s("sig")) {
            Ok(true) => added = true,
            Ok(false) => {}
            Err(err) => crate::log::line(format!("jobs: ignored a task from ntfy: {err}")),
        }
    }
    if let Some(id) = last_id {
        let _ = std::fs::write(since_path(), id);
    }
    if added {
        let _ = app.emit("jobs-changed", ());
    }
}

async fn run_due(app: &AppHandle) {
    let jobs = app.state::<Jobs>();
    if jobs.running.swap(true, Ordering::SeqCst) {
        return;
    }
    while let Some(job) = jobs.next_due() {
        jobs.set(&job.id, "running", "");
        let _ = app.emit("job", json!({ "status": "running", "instruction": job.instruction }));
        let model = app.state::<crate::Shared>().settings.lock().unwrap().model.clone();
        let prompt = format!(
            "A task the user left from their phone{}: \"{}\"\nDo it now on this PC with your tools. \
             When you're done, reply with one or two plain sentences saying what you did (or why you couldn't).",
            if job.run_at.is_some() { " for this time" } else { " while the PC was off" },
            job.instruction
        );
        let chat = claude::Chat::default();
        UNATTENDED.store(true, Ordering::SeqCst);
        let result = claude::send(app, &chat, &model, prompt, None).await;
        UNATTENDED.store(false, Ordering::SeqCst);
        let (status, text) = match result {
            Ok(reply) => ("done", reply.text),
            Err(err) => ("failed", err),
        };
        jobs.set(&job.id, status, &text);
        let _ = app.emit("job", json!({ "status": status, "instruction": job.instruction, "result": text }));
        let title = if status == "done" { "✅ Done on your PC" } else { "⚠️ Couldn't finish on your PC" };
        push::send_now(app, title, &format!("{}\n{}", job.instruction, text));
    }
    jobs.running.store(false, Ordering::SeqCst);
}
