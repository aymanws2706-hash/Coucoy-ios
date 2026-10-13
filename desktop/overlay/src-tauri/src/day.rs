// Personal build: "Your day" — weather from Open-Meteo (free, no key) and the
// next events from the user's calendar through its private iCal link (Google:
// "Secret address in iCal format"; Outlook: "Publish calendar" → ICS link).
// Both are cached so the island can ask as often as it likes.

use std::sync::Mutex;
use std::time::{Duration, Instant};

use serde::Serialize;
use serde_json::Value;

use crate::secrets;

const WEATHER_TTL: Duration = Duration::from_secs(15 * 60);
const PLACE_TTL: Duration = Duration::from_secs(6 * 3600);
const CALENDAR_TTL: Duration = Duration::from_secs(10 * 60);
/// How far ahead the calendar looks.
const LOOKAHEAD_DAYS: i64 = 7;

#[derive(Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct Hour {
    /// Local hour, 0–23.
    pub hour: u32,
    pub temp: f64,
    pub code: i64,
    /// Chance of rain, %.
    pub rain: i64,
}

#[derive(Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct Weather {
    pub city: String,
    pub temp: f64,
    pub code: i64,
    pub is_day: bool,
    pub high: f64,
    pub low: f64,
    pub hours: Vec<Hour>,
}

#[derive(Serialize, Clone, Debug, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct Event {
    pub title: String,
    /// Real epoch milliseconds, so the page's Date shows it in local time.
    pub start_ms: i64,
    pub end_ms: i64,
    pub all_day: bool,
    pub location: String,
}

#[derive(Clone)]
struct Place {
    name: String,
    lat: f64,
    lon: f64,
}

#[derive(Default)]
pub struct Day {
    place: Mutex<Option<(Instant, String, Place)>>,
    weather: Mutex<Option<(Instant, Weather)>>,
    calendar: Mutex<Option<(Instant, String, Vec<Event>)>>,
}

fn client() -> Result<reqwest::Client, String> {
    reqwest::Client::builder()
        .timeout(Duration::from_secs(15))
        .user_agent("Coucou-personal/1.0")
        .build()
        .map_err(|e| e.to_string())
}

async fn get_json(url: &str) -> Result<Value, String> {
    let resp = client()?.get(url).send().await.map_err(|e| format!("Network error: {e}"))?;
    if !resp.status().is_success() {
        return Err(format!("{url} answered {}", resp.status()));
    }
    resp.json().await.map_err(|e| e.to_string())
}

fn encode(s: &str) -> String {
    s.bytes()
        .map(|b| match b {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => (b as char).to_string(),
            _ => format!("%{b:02X}"),
        })
        .collect()
}

impl Day {
    /// The city typed in Settings, or wherever the internet connection is.
    async fn place(&self) -> Result<Place, String> {
        let wanted = secrets::get("weather-city").unwrap_or_default().trim().to_string();
        if let Some((at, key, p)) = self.place.lock().unwrap().clone() {
            if key == wanted && at.elapsed() < PLACE_TTL {
                return Ok(p);
            }
        }
        let place = if wanted.is_empty() {
            let v = get_json("https://ipwho.is/").await?;
            let lat = v.get("latitude").and_then(Value::as_f64);
            let lon = v.get("longitude").and_then(Value::as_f64);
            match (lat, lon) {
                (Some(lat), Some(lon)) => Place {
                    name: v.get("city").and_then(Value::as_str).unwrap_or("").to_string(),
                    lat,
                    lon,
                },
                _ => return Err("Couldn't tell where you are. Set a city in Settings › Your day.".into()),
            }
        } else {
            let url = format!(
                "https://geocoding-api.open-meteo.com/v1/search?count=1&name={}",
                encode(&wanted)
            );
            let v = get_json(&url).await?;
            let r = v
                .get("results")
                .and_then(Value::as_array)
                .and_then(|a| a.first())
                .ok_or_else(|| format!("No place called “{wanted}”."))?;
            Place {
                name: r.get("name").and_then(Value::as_str).unwrap_or(&wanted).to_string(),
                lat: r.get("latitude").and_then(Value::as_f64).unwrap_or(0.0),
                lon: r.get("longitude").and_then(Value::as_f64).unwrap_or(0.0),
            }
        };
        *self.place.lock().unwrap() = Some((Instant::now(), wanted, place.clone()));
        Ok(place)
    }

    pub async fn weather(&self, force: bool) -> Result<Weather, String> {
        if !force {
            if let Some((at, w)) = self.weather.lock().unwrap().clone() {
                if at.elapsed() < WEATHER_TTL {
                    return Ok(w);
                }
            }
        }
        let place = self.place().await?;
        let url = format!(
            "https://api.open-meteo.com/v1/forecast?latitude={:.4}&longitude={:.4}\
             &current=temperature_2m,weather_code,is_day\
             &hourly=temperature_2m,weather_code,precipitation_probability\
             &daily=temperature_2m_max,temperature_2m_min\
             &forecast_hours=7&forecast_days=1&timezone=auto",
            place.lat, place.lon
        );
        let v = get_json(&url).await?;
        let w = parse_weather(&v, &place.name).ok_or("Weather service sent something unexpected.")?;
        *self.weather.lock().unwrap() = Some((Instant::now(), w.clone()));
        Ok(w)
    }

    pub async fn calendar(&self, force: bool) -> Result<Vec<Event>, String> {
        let Some(url) = secrets::get("calendar-ics-url") else {
            return Ok(Vec::new());
        };
        let url = url.trim().replacen("webcal://", "https://", 1);
        if !force {
            if let Some((at, key, events)) = self.calendar.lock().unwrap().clone() {
                if key == url && at.elapsed() < CALENDAR_TTL {
                    return Ok(still_ahead(events));
                }
            }
        }
        let resp = client()?.get(&url).send().await.map_err(|e| format!("Network error: {e}"))?;
        if !resp.status().is_success() {
            return Err(format!("The calendar link answered {}.", resp.status()));
        }
        let text = resp.text().await.map_err(|e| e.to_string())?;
        if !text.contains("BEGIN:VCALENDAR") {
            return Err("That link isn't an iCal calendar.".into());
        }
        let now_utc = now_secs();
        let offset = local_offset_secs();
        let events = upcoming(&text, now_utc, offset, LOOKAHEAD_DAYS);
        *self.calendar.lock().unwrap() = Some((Instant::now(), url, events.clone()));
        Ok(events)
    }
}

fn still_ahead(events: Vec<Event>) -> Vec<Event> {
    let now = now_secs() * 1000;
    events.into_iter().filter(|e| e.end_ms > now).collect()
}

fn parse_weather(v: &Value, city: &str) -> Option<Weather> {
    let cur = v.get("current")?;
    let hourly = v.get("hourly")?;
    let daily = v.get("daily")?;
    let arr = |o: &Value, k: &str| o.get(k).and_then(Value::as_array).cloned().unwrap_or_default();
    let times = arr(hourly, "time");
    let temps = arr(hourly, "temperature_2m");
    let codes = arr(hourly, "weather_code");
    let rains = arr(hourly, "precipitation_probability");
    let hours = times
        .iter()
        .enumerate()
        .skip(1) // the first one is the current hour, already shown big
        .take(6)
        .map(|(i, t)| Hour {
            hour: t.as_str().and_then(|s| s.get(11..13)).and_then(|h| h.parse().ok()).unwrap_or(0),
            temp: temps.get(i).and_then(Value::as_f64).unwrap_or(0.0),
            code: codes.get(i).and_then(Value::as_i64).unwrap_or(0),
            rain: rains.get(i).and_then(Value::as_i64).unwrap_or(0),
        })
        .collect();
    Some(Weather {
        city: city.to_string(),
        temp: cur.get("temperature_2m")?.as_f64()?,
        code: cur.get("weather_code").and_then(Value::as_i64).unwrap_or(0),
        is_day: cur.get("is_day").and_then(Value::as_i64).unwrap_or(1) == 1,
        high: arr(daily, "temperature_2m_max").first().and_then(Value::as_f64).unwrap_or(0.0),
        low: arr(daily, "temperature_2m_min").first().and_then(Value::as_f64).unwrap_or(0.0),
        hours,
    })
}

// ── Time helpers (no time-zone database: iCal times with a TZID are read as
// local time, which is right for a personal calendar) ────────────────────────

fn now_secs() -> i64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

/// Local time minus UTC, in seconds, rounded to the quarter hour.
fn local_offset_secs() -> i64 {
    let t = crate::platform::local_time();
    let local = civil_to_secs(t.year as i64, t.month as i64, t.day as i64, t.hour as i64, t.minute as i64, t.second as i64);
    let diff = local - now_secs();
    ((diff as f64 / 900.0).round() as i64) * 900
}

/// "Tue 2026-10-14 09:00" in local time, for the assistant.
pub fn local_label(ms: i64) -> String {
    const WD: [&str; 7] = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
    let local = ms / 1000 + local_offset_secs();
    let days = local.div_euclid(86400);
    let (y, m, d) = civil_from_days(days);
    let tod = local.rem_euclid(86400);
    format!("{} {y:04}-{m:02}-{d:02} {:02}:{:02}", WD[weekday(days) as usize], tod / 3600, tod % 3600 / 60)
}

/// Days since 1970-01-01 for a civil date (Howard Hinnant's algorithm).
fn days_from_civil(y: i64, m: i64, d: i64) -> i64 {
    let y = if m <= 2 { y - 1 } else { y };
    let era = if y >= 0 { y } else { y - 399 } / 400;
    let yoe = y - era * 400;
    let mp = (m + 9) % 12;
    let doy = (153 * mp + 2) / 5 + d - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    era * 146097 + doe - 719468
}

fn civil_from_days(z: i64) -> (i64, i64, i64) {
    let z = z + 719468;
    let era = if z >= 0 { z } else { z - 146096 } / 146097;
    let doe = z - era * 146097;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    (if m <= 2 { y + 1 } else { y }, m, d)
}

fn civil_to_secs(y: i64, mo: i64, d: i64, h: i64, mi: i64, s: i64) -> i64 {
    days_from_civil(y, mo, d) * 86400 + h * 3600 + mi * 60 + s
}

/// 0 = Monday … 6 = Sunday.
fn weekday(days: i64) -> i64 {
    (days + 3).rem_euclid(7)
}

// ── iCal ─────────────────────────────────────────────────────────────────────

/// A parsed date-time in "local seconds" (local wall clock as if it were UTC).
#[derive(Clone, Copy)]
struct When {
    local: i64,
    all_day: bool,
}

fn parse_when(params: &str, value: &str, offset: i64) -> Option<When> {
    let v = value.trim();
    let num = |a: usize, b: usize| v.get(a..b).and_then(|s| s.parse::<i64>().ok());
    let (y, mo, d) = (num(0, 4)?, num(4, 6)?, num(6, 8)?);
    if v.len() == 8 || params.contains("VALUE=DATE") && !params.contains("VALUE=DATE-TIME") {
        return Some(When { local: civil_to_secs(y, mo, d, 0, 0, 0), all_day: true });
    }
    let (h, mi, s) = (num(9, 11)?, num(11, 13)?, num(13, 15).unwrap_or(0));
    let mut local = civil_to_secs(y, mo, d, h, mi, s);
    if v.ends_with('Z') {
        local += offset;
    }
    Some(When { local, all_day: false })
}

struct RawEvent {
    summary: String,
    location: String,
    start: When,
    duration: i64,
    rrule: Option<String>,
    exdates: Vec<i64>,
    cancelled: bool,
}

fn unescape(s: &str) -> String {
    s.replace("\\n", " ").replace("\\N", " ").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")
}

fn parse_events(text: &str, offset: i64) -> Vec<RawEvent> {
    // Unfold: a line starting with a space or tab continues the previous one.
    let mut lines: Vec<String> = Vec::new();
    for raw in text.split('\n') {
        let raw = raw.trim_end_matches('\r');
        if (raw.starts_with(' ') || raw.starts_with('\t')) && !lines.is_empty() {
            lines.last_mut().unwrap().push_str(&raw[1..]);
        } else {
            lines.push(raw.to_string());
        }
    }

    let mut out = Vec::new();
    let mut cur: Option<(String, String, Option<When>, Option<When>, Option<String>, Vec<i64>, bool, bool)> = None;
    for line in lines {
        if line == "BEGIN:VEVENT" {
            cur = Some((String::new(), String::new(), None, None, None, Vec::new(), false, false));
            continue;
        }
        if line == "END:VEVENT" {
            if let Some((summary, location, start, end, rrule, exdates, cancelled, is_override)) = cur.take() {
                let Some(start) = start else { continue };
                let duration = match end {
                    Some(e) => (e.local - start.local).max(0),
                    None if start.all_day => 86400,
                    None => 3600,
                };
                // A moved single occurrence of a series: keep it as its own event.
                let rrule = if is_override { None } else { rrule };
                out.push(RawEvent { summary, location, start, duration, rrule, exdates, cancelled });
            }
            continue;
        }
        let Some(ev) = cur.as_mut() else { continue };
        let Some((head, value)) = line.split_once(':') else { continue };
        let (name, params) = head.split_once(';').unwrap_or((head, ""));
        match name {
            "SUMMARY" => ev.0 = unescape(value),
            "LOCATION" => ev.1 = unescape(value),
            "DTSTART" => ev.2 = parse_when(params, value, offset),
            "DTEND" => ev.3 = parse_when(params, value, offset),
            "RRULE" => ev.4 = Some(value.to_string()),
            "EXDATE" => {
                for part in value.split(',') {
                    if let Some(w) = parse_when(params, part, offset) {
                        ev.5.push(w.local);
                    }
                }
            }
            "STATUS" => ev.6 = value.trim() == "CANCELLED",
            "RECURRENCE-ID" => ev.7 = true,
            _ => {}
        }
    }
    out
}

const DAY_NAMES: [&str; 7] = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"];

/// Start times (local seconds) of one event that fall in [from, to).
fn occurrences(ev: &RawEvent, from: i64, to: i64, offset: i64) -> Vec<i64> {
    let start = ev.start.local;
    let Some(rule) = &ev.rrule else {
        return if start + ev.duration.max(1) > from && start < to { vec![start] } else { vec![] };
    };
    let mut freq = "";
    let mut interval = 1i64;
    let mut count: Option<i64> = None;
    let mut until: Option<i64> = None;
    let mut byday: Vec<i64> = Vec::new();
    for part in rule.split(';') {
        let Some((k, v)) = part.split_once('=') else { continue };
        match k {
            "FREQ" => freq = v,
            "INTERVAL" => interval = v.parse().unwrap_or(1).max(1),
            "COUNT" => count = v.parse().ok(),
            "UNTIL" => until = parse_when("", v, offset).map(|w| w.local + if w.all_day { 86399 } else { 0 }),
            "BYDAY" => {
                for d in v.split(',') {
                    let code = d.trim_start_matches(|c: char| c == '-' || c == '+' || c.is_ascii_digit());
                    if let Some(i) = DAY_NAMES.iter().position(|n| *n == code) {
                        byday.push(i as i64);
                    }
                }
            }
            _ => {}
        }
    }

    let tod = start.rem_euclid(86400);
    let start_day = start.div_euclid(86400);
    let (sy, sm, sd) = civil_from_days(start_day);
    let mut out = Vec::new();
    let mut produced = 0i64;
    let mut emit = |t: i64, out: &mut Vec<i64>| -> bool {
        // Returns false once the series is over.
        if let Some(u) = until {
            if t > u {
                return false;
            }
        }
        if let Some(c) = count {
            if produced >= c {
                return false;
            }
        }
        produced += 1;
        if t + ev.duration.max(1) > from && t < to && !ev.exdates.contains(&t) {
            out.push(t);
        }
        t < to
    };

    match freq {
        "DAILY" => {
            let mut day = start_day;
            for _ in 0..20_000 {
                if !emit(day * 86400 + tod, &mut out) {
                    break;
                }
                day += interval;
            }
        }
        "WEEKLY" => {
            let days = if byday.is_empty() { vec![weekday(start_day)] } else { byday.clone() };
            let week0 = start_day - weekday(start_day);
            let mut week = week0;
            'outer: for _ in 0..5_000 {
                let mut ds = days.clone();
                ds.sort();
                for wd in ds {
                    let day = week + wd;
                    if day < start_day {
                        continue;
                    }
                    if !emit(day * 86400 + tod, &mut out) {
                        break 'outer;
                    }
                }
                week += 7 * interval;
            }
        }
        "MONTHLY" => {
            let mut k = 0i64;
            for _ in 0..2_000 {
                let total = (sm - 1) + k * interval;
                let (y, m) = (sy + total.div_euclid(12), total.rem_euclid(12) + 1);
                // Skip months that don't have this day (the 31st in April).
                let (cy, cm, _) = civil_from_days(days_from_civil(y, m, sd));
                if cy == y && cm == m && !emit(days_from_civil(y, m, sd) * 86400 + tod, &mut out) {
                    break;
                }
                k += 1;
            }
        }
        "YEARLY" => {
            let mut k = 0i64;
            for _ in 0..500 {
                let y = sy + k * interval;
                let (cy, cm, _) = civil_from_days(days_from_civil(y, sm, sd));
                if cy == y && cm == sm && !emit(days_from_civil(y, sm, sd) * 86400 + tod, &mut out) {
                    break;
                }
                k += 1;
            }
        }
        _ => {
            if start + ev.duration.max(1) > from && start < to {
                out.push(start);
            }
        }
    }
    out
}

fn upcoming(text: &str, now_utc: i64, offset: i64, days: i64) -> Vec<Event> {
    let now_local = now_utc + offset;
    let to = now_local + days * 86400;
    let mut events: Vec<Event> = Vec::new();
    for ev in parse_events(text, offset) {
        if ev.cancelled {
            continue;
        }
        for t in occurrences(&ev, now_local, to, offset) {
            events.push(Event {
                title: if ev.summary.is_empty() { "(no title)".into() } else { ev.summary.clone() },
                start_ms: (t - offset) * 1000,
                end_ms: (t + ev.duration - offset) * 1000,
                all_day: ev.start.all_day,
                location: ev.location.clone(),
            });
        }
    }
    events.sort_by_key(|e| e.start_ms);
    events.dedup_by(|a, b| a.title == b.title && a.start_ms == b.start_ms);
    events.truncate(12);
    events
}

#[cfg(test)]
mod tests {
    use super::*;

    const ICS: &str = "BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nDTSTART:20261014T090000Z\r\nDTEND:20261014T100000Z\r\nSUMMARY:Stand-up\r\nRRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR\r\nEND:VEVENT\r\nBEGIN:VEVENT\r\nDTSTART;VALUE=DATE:20261016\r\nSUMMARY:Holiday\\, beach\r\nEND:VEVENT\r\nBEGIN:VEVENT\r\nDTSTART;TZID=Africa/Casablanca:20261013T180000\r\nDTEND;TZID=Africa/Casablanca:20261013T190000\r\nSUMMARY:Gym\r\nLOCATION:Downtown\r\nEND:VEVENT\r\nBEGIN:VEVENT\r\nDTSTART:20261013T080000Z\r\nSUMMARY:Already over\r\nDTEND:20261013T083000Z\r\nEND:VEVENT\r\nBEGIN:VEVENT\r\nDTSTART:20261015T120000Z\r\nSUMMARY:Lunch \r\n with Sam\r\nSTATUS:CANCELLED\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n";

    #[test]
    fn upcoming_week() {
        // 2026-10-13 12:00 UTC, local = UTC+1.
        let now = civil_to_secs(2026, 10, 13, 12, 0, 0);
        let ev = upcoming(ICS, now, 3600, 7);
        let titles: Vec<_> = ev.iter().map(|e| e.title.as_str()).collect();
        // Cancelled lunch and the event already over are left out; the window ends
        // on the 20th at noon, so Wednesday the 21st is not in it.
        assert_eq!(titles, ["Gym", "Stand-up", "Holiday, beach", "Stand-up", "Stand-up"]);
        // Gym is local 18:00 at UTC+1 → 17:00 UTC.
        assert_eq!(ev[0].start_ms, civil_to_secs(2026, 10, 13, 17, 0, 0) * 1000);
        assert_eq!(ev[0].location, "Downtown");
        assert!(ev[2].all_day);
        // Stand-up 09:00Z every Mon/Wed/Fri from Wed 14th: 14, 16, 19.
        assert_eq!(ev[1].start_ms, civil_to_secs(2026, 10, 14, 9, 0, 0) * 1000);
        assert_eq!(ev[3].start_ms, civil_to_secs(2026, 10, 16, 9, 0, 0) * 1000);
    }

    #[test]
    fn civil_roundtrip() {
        for d in [-1000, 0, 1, 20_000, 20_739] {
            let (y, m, dd) = civil_from_days(d);
            assert_eq!(days_from_civil(y, m, dd), d);
        }
        assert_eq!(weekday(days_from_civil(2026, 10, 13)), 1); // Tuesday
    }
}
