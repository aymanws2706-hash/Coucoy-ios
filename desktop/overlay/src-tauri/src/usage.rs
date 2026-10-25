// Personal build: where the day went. Every 5 s while the PC is in use, the
// app in front gets 5 s; for Revit, the open project too (from the window
// title). It feeds the evening recap, the "time on a project" question in the
// chat, and the Revit save reminder. Only app and project names are kept, on
// this PC, for 35 days. Tray › Pause stops it.

use std::collections::{BTreeMap, HashMap};
use std::sync::atomic::Ordering;
use std::sync::Mutex;
use std::time::{Duration, Instant, SystemTime};

use serde::{Deserialize, Serialize};
use serde_json::json;
use tauri::{AppHandle, Emitter, Manager};

use crate::platform;

const TICK: u64 = 5;
/// Revit in use this long since the last save → a reminder.
const SAVE_NAG_MINS: u64 = 40;

#[derive(Serialize, Deserialize, Default, Clone)]
#[serde(default)]
pub struct Day {
    /// App (exe name) → seconds in front.
    pub apps: BTreeMap<String, u64>,
    /// Revit project → seconds.
    pub revit: BTreeMap<String, u64>,
    /// First and last minute of use, "HH:MM".
    pub first: String,
    pub last: String,
}

#[derive(Default)]
pub struct Usage {
    days: Mutex<Option<BTreeMap<String, Day>>>,
}

fn path() -> std::path::PathBuf {
    platform::local_dir().join("usage.json")
}

fn today_key() -> String {
    let t = platform::local_time();
    format!("{:04}-{:02}-{:02}", t.year, t.month, t.day)
}

impl Usage {
    fn with<R>(&self, f: impl FnOnce(&mut BTreeMap<String, Day>) -> R) -> R {
        let mut g = self.days.lock().unwrap();
        if g.is_none() {
            *g = Some(
                std::fs::read(path())
                    .ok()
                    .and_then(|b| serde_json::from_slice(&b).ok())
                    .unwrap_or_default(),
            );
        }
        f(g.as_mut().unwrap())
    }

    fn save(&self) {
        self.with(|d| {
            while d.len() > 35 {
                let first = d.keys().next().cloned().unwrap();
                d.remove(&first);
            }
            let _ = platform::ensure_private_dir(&platform::local_dir());
            if let Ok(json) = serde_json::to_vec(d) {
                let _ = std::fs::write(path(), json);
            }
        });
    }

    pub fn today(&self) -> Day {
        let key = today_key();
        self.with(|d| d.get(&key).cloned().unwrap_or_default())
    }

    /// The last `days` days, newest first.
    pub fn recent(&self, days: usize) -> Vec<(String, Day)> {
        self.with(|d| d.iter().rev().take(days).map(|(k, v)| (k.clone(), v.clone())).collect())
    }
}

/// "Projet_Villa_v3" from "Autodesk Revit 2025.1 - [Projet_Villa_v3.rvt - Floor Plan: Level 1]".
pub fn revit_project(title: &str) -> Option<String> {
    let inner = title.split_once('[')?.1;
    let inner = inner.rsplit_once(']').map(|(a, _)| a).unwrap_or(inner);
    let name = inner.split(" - ").next()?.trim();
    let name = name.trim_end_matches(".rvt").trim_end_matches(".RVT").trim();
    (!name.is_empty()).then(|| name.to_string())
}

fn is_revit(exe: &str) -> bool {
    exe.to_lowercase().contains("revit")
}

/// The .rvt with this name in the user's usual folders (searched once per project).
fn find_rvt(project: &str) -> Option<std::path::PathBuf> {
    let home = std::env::var_os("USERPROFILE").map(std::path::PathBuf::from)?;
    let want = format!("{}.rvt", project.to_lowercase());
    let mut roots: Vec<std::path::PathBuf> =
        ["Documents", "Desktop", "Downloads", "OneDrive"].iter().map(|f| home.join(f)).collect();
    if let Ok(entries) = std::fs::read_dir(&home) {
        roots.extend(
            entries
                .flatten()
                .map(|e| e.path())
                .filter(|p| p.file_name().map(|n| n.to_string_lossy().starts_with("OneDrive")).unwrap_or(false)),
        );
    }
    let mut stack: Vec<(std::path::PathBuf, u32)> = roots.into_iter().map(|r| (r, 0)).collect();
    let mut seen = 0;
    while let Some((dir, depth)) = stack.pop() {
        let Ok(entries) = std::fs::read_dir(&dir) else { continue };
        for e in entries.flatten() {
            seen += 1;
            if seen > 60_000 {
                return None;
            }
            let p = e.path();
            let Ok(ft) = e.file_type() else { continue };
            if ft.is_dir() {
                if depth < 7 && !p.file_name().map(|n| n.to_string_lossy().starts_with('.')).unwrap_or(true) {
                    stack.push((p, depth + 1));
                }
            } else if p.file_name().map(|n| n.to_string_lossy().to_lowercase() == want).unwrap_or(false) {
                return Some(p);
            }
        }
    }
    None
}

struct Revit {
    /// Project → (file, when it was last found saved, seconds of use since then, last nag).
    files: HashMap<String, Option<std::path::PathBuf>>,
    since_save: HashMap<String, (SystemTime, u64)>,
    nagged: HashMap<String, Instant>,
}

pub fn start(app: AppHandle) {
    std::thread::spawn(move || {
        let mut revit = Revit { files: HashMap::new(), since_save: HashMap::new(), nagged: HashMap::new() };
        let mut ticks: u64 = 0;
        loop {
            std::thread::sleep(Duration::from_secs(TICK));
            ticks += 1;
            if crate::integrations::PAUSED.load(Ordering::Relaxed) || crate::awareness::idle_secs() > 120 {
                continue;
            }
            let Some((exe, title)) = crate::awareness::foreground_app() else { continue };
            if exe.is_empty() || exe.eq_ignore_ascii_case("LockApp") {
                continue;
            }
            let t = platform::local_time();
            let hm = format!("{:02}:{:02}", t.hour, t.minute);
            let project = if is_revit(&exe) { revit_project(&title) } else { None };
            let usage = app.state::<Usage>();
            let key = today_key();
            usage.with(|d| {
                let day = d.entry(key).or_default();
                *day.apps.entry(exe.clone()).or_default() += TICK;
                if let Some(p) = &project {
                    *day.revit.entry(p.clone()).or_default() += TICK;
                }
                if day.first.is_empty() {
                    day.first = hm.clone();
                }
                day.last = hm;
            });
            if ticks % 12 == 0 {
                usage.save();
            }
            if let Some(p) = project {
                check_save(&app, &mut revit, &p);
            }
        }
    });
}

fn check_save(app: &AppHandle, revit: &mut Revit, project: &str) {
    let file = revit.files.entry(project.to_string()).or_insert_with(|| find_rvt(project)).clone();
    let Some(file) = file else { return };
    let Ok(saved) = std::fs::metadata(&file).and_then(|m| m.modified()) else { return };
    let entry = revit.since_save.entry(project.to_string()).or_insert((saved, 0));
    if entry.0 != saved {
        *entry = (saved, 0);
    }
    entry.1 += TICK;
    let mins = entry.1 / 60;
    let quiet = revit.nagged.get(project).map(|t| t.elapsed() < Duration::from_secs(20 * 60)).unwrap_or(false);
    if mins >= SAVE_NAG_MINS && !quiet {
        revit.nagged.insert(project.to_string(), Instant::now());
        let _ = app.emit("revit-save", json!({ "project": project, "minutes": mins }));
    }
}

/// For the chat: hours per app and per Revit project over the last days.
pub fn report(app: &AppHandle, days: usize) -> String {
    let list = app.state::<Usage>().recent(days.clamp(1, 35));
    if list.is_empty() {
        return "No usage recorded yet (Putshi counts the app in front while the PC is in use).".into();
    }
    let fmt = |s: u64| format!("{}h{:02}", s / 3600, (s % 3600) / 60);
    let mut apps: BTreeMap<String, u64> = BTreeMap::new();
    let mut projects: BTreeMap<String, u64> = BTreeMap::new();
    let mut lines = Vec::new();
    for (date, d) in &list {
        let total: u64 = d.apps.values().sum();
        lines.push(format!("{date}: {} at the PC ({}–{})", fmt(total), d.first, d.last));
        for (k, v) in &d.apps {
            *apps.entry(k.clone()).or_default() += v;
        }
        for (k, v) in &d.revit {
            *projects.entry(k.clone()).or_default() += v;
        }
    }
    let mut a: Vec<_> = apps.into_iter().collect();
    a.sort_by(|x, y| y.1.cmp(&x.1));
    let mut p: Vec<_> = projects.into_iter().collect();
    p.sort_by(|x, y| y.1.cmp(&x.1));
    format!(
        "Days:\n{}\n\nApps:\n{}\n\nRevit projects:\n{}",
        lines.join("\n"),
        a.iter().take(12).map(|(k, v)| format!("{k}: {}", fmt(*v))).collect::<Vec<_>>().join("\n"),
        if p.is_empty() { "(none)".into() } else { p.iter().map(|(k, v)| format!("{k}: {}", fmt(*v))).collect::<Vec<_>>().join("\n") },
    )
}

#[cfg(test)]
mod tests {
    #[test]
    fn revit_titles() {
        use super::revit_project;
        assert_eq!(revit_project("Autodesk Revit 2025.1 - [Projet_Villa_v3.rvt - Floor Plan: Level 1]").as_deref(), Some("Projet_Villa_v3"));
        assert_eq!(revit_project("Autodesk Revit 2023 - [Maison R+1 - 3D View: {3D}]").as_deref(), Some("Maison R+1"));
        assert_eq!(revit_project("Autodesk Revit 2024"), None);
    }
}
