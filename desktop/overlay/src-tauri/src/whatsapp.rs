// Personal build: WhatsApp, the safe way. WhatsApp has no official access to a
// personal account, so Putshi never logs in to it:
//   reading — the WhatsApp notifications Windows keeps in its notification
//             centre (who wrote and the preview), only when switched on in
//             Settings › Awareness;
//   writing — opens WhatsApp with the message already typed; the user presses
//             Send.

use std::collections::VecDeque;
use std::sync::Mutex;

use serde::Serialize;

#[derive(Serialize, Clone, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct Message {
    pub id: i64,
    /// The chat: a person or a group.
    pub chat: String,
    pub text: String,
    /// Unix seconds.
    pub at: i64,
}

#[derive(Default)]
pub struct WhatsApp {
    seen: Mutex<VecDeque<Message>>,
    last_id: Mutex<i64>,
}

impl WhatsApp {
    /// Messages that arrived since the last call (the first call only primes).
    pub fn fresh(&self) -> Vec<Message> {
        let Ok(all) = imp::notifications() else { return Vec::new() };
        let mut last = self.last_id.lock().unwrap();
        let primed = *last != 0;
        let new: Vec<Message> = all.iter().filter(|m| m.id > *last).cloned().collect();
        if let Some(max) = all.iter().map(|m| m.id).max() {
            *last = (*last).max(max).max(1);
        } else if !primed {
            *last = 1;
        }
        let mut seen = self.seen.lock().unwrap();
        for m in &new {
            if !seen.contains(m) {
                seen.push_back(m.clone());
            }
        }
        while seen.len() > 60 {
            seen.pop_front();
        }
        if primed { new } else { Vec::new() }
    }

    /// Recent messages, newest first: what's still in the notification centre
    /// plus what Putshi saw earlier this session.
    pub fn recent(&self) -> Result<Vec<Message>, String> {
        let now = imp::notifications().unwrap_or_default();
        let mut all: Vec<Message> = self.seen.lock().unwrap().iter().cloned().collect();
        for m in now {
            if !all.contains(&m) {
                all.push(m);
            }
        }
        all.sort_by(|a, b| b.at.cmp(&a.at).then(b.id.cmp(&a.id)));
        all.truncate(40);
        Ok(all)
    }
}

/// "5 min ago", "yesterday 18:02"-ish, for Claude.
pub fn describe(list: &[Message]) -> String {
    if list.is_empty() {
        return "No WhatsApp notifications right now. (Windows only keeps them until they're opened or cleared, and WhatsApp doesn't send any while its window is in front.)".into();
    }
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);
    list.iter()
        .map(|m| {
            let mins = ((now - m.at) / 60).max(0);
            let ago = match mins {
                0 => "just now".to_string(),
                1..=59 => format!("{mins} min ago"),
                60..=1439 => format!("{} h ago", mins / 60),
                _ => format!("{} days ago", mins / 1440),
            };
            format!("[{ago}] {}: {}", m.chat, m.text)
        })
        .collect::<Vec<_>>()
        .join("\n")
}

/// Opens WhatsApp with `text` typed in. With a number (international, like
/// +212612345678) it opens that chat; without one WhatsApp asks who to send it to.
pub fn draft(phone: &str, text: &str) -> Result<String, String> {
    let digits: String = phone.chars().filter(char::is_ascii_digit).collect();
    if !phone.trim().is_empty() && digits.len() < 8 {
        return Err("Give the number with its country code, like +212612345678.".into());
    }
    let mut url = String::from("whatsapp://send?");
    if !digits.is_empty() {
        url.push_str(&format!("phone={digits}&"));
    }
    url.push_str(&format!("text={}", encode(text)));
    imp::open_url(&url)?;
    Ok(if digits.is_empty() {
        "WhatsApp is open with the message typed; the user picks the chat and presses Send.".into()
    } else {
        "WhatsApp is open on that chat with the message typed; the user presses Send.".into()
    })
}

fn encode(s: &str) -> String {
    let mut out = String::new();
    for b in s.bytes() {
        match b {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => out.push(b as char),
            _ => out.push_str(&format!("%{b:02X}")),
        }
    }
    out
}

/// The texts of a toast's XML: the first is the chat, the rest the message.
fn parse_toast(xml: &str) -> Option<(String, String)> {
    let mut texts = Vec::new();
    let mut rest = xml;
    while let Some(i) = rest.find("<text") {
        rest = &rest[i + 5..];
        // Skip <textBox and friends.
        if !rest.starts_with('>') && !rest.starts_with(' ') && !rest.starts_with('/') {
            continue;
        }
        let Some(gt) = rest.find('>') else { break };
        if rest[..gt].ends_with('/') {
            rest = &rest[gt + 1..];
            continue;
        }
        let body = &rest[gt + 1..];
        let Some(end) = body.find("</text>") else { break };
        let t = unescape(&body[..end]);
        if !t.trim().is_empty() {
            texts.push(t.trim().to_string());
        }
        rest = &body[end..];
    }
    let mut it = texts.into_iter();
    let chat = it.next()?;
    let text = it.collect::<Vec<_>>().join(" — ");
    Some((chat, text))
}

fn unescape(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let mut rest = s;
    while let Some(i) = rest.find('&') {
        out.push_str(&rest[..i]);
        rest = &rest[i..];
        let Some(semi) = rest.find(';').filter(|&j| j <= 10) else {
            out.push('&');
            rest = &rest[1..];
            continue;
        };
        let ent = &rest[1..semi];
        let ch = match ent {
            "amp" => Some('&'),
            "lt" => Some('<'),
            "gt" => Some('>'),
            "quot" => Some('"'),
            "apos" => Some('\''),
            _ if ent.starts_with("#x") => u32::from_str_radix(&ent[2..], 16).ok().and_then(char::from_u32),
            _ if ent.starts_with('#') => ent[1..].parse().ok().and_then(char::from_u32),
            _ => None,
        };
        match ch {
            Some(c) => {
                out.push(c);
                rest = &rest[semi + 1..];
            }
            None => {
                out.push('&');
                rest = &rest[1..];
            }
        }
    }
    out.push_str(rest);
    out
}

#[cfg(windows)]
mod imp {
    use super::{parse_toast, Message};
    use rusqlite::{Connection, OpenFlags};

    /// WhatsApp's notifications from Windows' notification database. The
    /// database is in use, so it's read from a private copy that's deleted
    /// right after.
    pub fn notifications() -> Result<Vec<Message>, String> {
        let local = std::env::var("LOCALAPPDATA").map_err(|e| e.to_string())?;
        let src = std::path::Path::new(&local).join("Microsoft\\Windows\\Notifications");
        let tmp = crate::platform::local_dir().join("wpn-copy");
        let _ = std::fs::create_dir_all(&tmp);
        let db = tmp.join("wpndatabase.db");
        let copied = std::fs::copy(src.join("wpndatabase.db"), &db).is_ok();
        if copied {
            for ext in ["-wal", "-shm"] {
                let _ = std::fs::copy(src.join(format!("wpndatabase.db{ext}")), tmp.join(format!("wpndatabase.db{ext}")));
            }
        }
        let path = if copied { db.clone() } else { src.join("wpndatabase.db") };
        let result = read(&path, !copied);
        let _ = std::fs::remove_dir_all(&tmp);
        result
    }

    fn read(path: &std::path::Path, read_only: bool) -> Result<Vec<Message>, String> {
        let flags = if read_only {
            OpenFlags::SQLITE_OPEN_READ_ONLY | OpenFlags::SQLITE_OPEN_NO_MUTEX
        } else {
            OpenFlags::SQLITE_OPEN_READ_WRITE | OpenFlags::SQLITE_OPEN_NO_MUTEX
        };
        let conn = Connection::open_with_flags(path, flags).map_err(|e| e.to_string())?;
        let mut stmt = conn
            .prepare(
                "SELECT n.Id, n.Payload, n.ArrivalTime FROM Notification n \
                 JOIN NotificationHandler h ON h.RecordId = n.HandlerId \
                 WHERE h.PrimaryId LIKE '%WhatsApp%' AND n.Type = 'toast' \
                 ORDER BY n.Id DESC LIMIT 60",
            )
            .map_err(|e| e.to_string())?;
        let rows = stmt
            .query_map([], |r| {
                let id: i64 = r.get(0)?;
                let payload: Vec<u8> = r.get(1).unwrap_or_default();
                let arrival: i64 = r.get(2).unwrap_or(0);
                Ok((id, payload, arrival))
            })
            .map_err(|e| e.to_string())?;
        let mut out = Vec::new();
        for (id, payload, arrival) in rows.flatten() {
            let xml = String::from_utf8_lossy(&payload);
            let Some((chat, text)) = parse_toast(&xml) else { continue };
            // FILETIME: 100 ns steps since 1601.
            let at = if arrival > 0 { arrival / 10_000_000 - 11_644_473_600 } else { 0 };
            out.push(Message { id, chat, text, at });
        }
        Ok(out)
    }

    pub fn open_url(url: &str) -> Result<(), String> {
        let mut cmd = std::process::Command::new("explorer.exe");
        cmd.arg(url);
        cmd.spawn().map(|_| ()).map_err(|e| format!("Couldn't open WhatsApp: {e}"))
    }
}

#[cfg(not(windows))]
mod imp {
    use super::Message;

    pub fn notifications() -> Result<Vec<Message>, String> {
        Err("WhatsApp notifications are read on Windows only.".into())
    }

    pub fn open_url(url: &str) -> Result<(), String> {
        std::process::Command::new("xdg-open").arg(url).spawn().map(|_| ()).map_err(|e| e.to_string())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reads_a_whatsapp_toast() {
        let xml = r#"<toast launch="x"><visual><binding template="ToastGeneric"><image placement="appLogoOverride" src="a.png"/><text hint-maxLines="1">Karim</text><text>Call me tonight &amp; bring the plans</text></binding></visual><actions><input id="reply" type="text"/></actions></toast>"#;
        let (chat, text) = parse_toast(xml).unwrap();
        assert_eq!(chat, "Karim");
        assert_eq!(text, "Call me tonight & bring the plans");
        assert_eq!(encode("Salut ça va?"), "Salut%20%C3%A7a%20va%3F");
    }
}
