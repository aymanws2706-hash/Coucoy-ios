// Personal build: the Live panel — Barça and Morocco (ESPN's public scores
// feed), Formula 1 (Jolpica, the Ergast successor) and the markets (Yahoo
// Finance charts and trending tickers, CoinGecko for crypto). All free, no
// account. Read every 15 minutes, every minute while a match is on; a goal
// for Barça or Morocco rings the notch and the phone.

use std::sync::Mutex;
use std::time::{Duration, Instant};

use serde::Serialize;
use serde_json::Value;
use tauri::{AppHandle, Emitter, Manager};

const BARCA: &str = "83";
/// ESPN leagues Barça plays in.
const BARCA_LEAGUES: &[&str] = &["esp.1", "uefa.champions", "esp.copa_del_rey", "esp.super_cup"];
/// ESPN competitions Morocco plays in.
const MOROCCO_LEAGUES: &[&str] = &["fifa.world", "fifa.worldq.caf", "caf.nations", "fifa.friendly", "caf.nations_qual"];

#[derive(Serialize, Clone, Default, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct Match {
    pub competition: String,
    pub home: String,
    pub away: String,
    pub home_score: Option<u32>,
    pub away_score: Option<u32>,
    /// "pre", "in" or "post".
    pub state: String,
    /// "67'", "HT", "FT", or the kick-off time as given.
    pub detail: String,
    /// Kick-off, Unix ms.
    pub start_ms: i64,
}

#[derive(Serialize, Clone, Default)]
#[serde(rename_all = "camelCase")]
pub struct Team {
    pub name: String,
    pub live: Option<Match>,
    pub last: Option<Match>,
    pub next: Option<Match>,
}

#[derive(Serialize, Clone, Default)]
#[serde(rename_all = "camelCase")]
pub struct F1 {
    pub next_race: Option<String>,
    pub next_place: Option<String>,
    /// Race start, Unix ms.
    pub next_ms: Option<i64>,
    pub last_race: Option<String>,
    /// "VER, NOR, LEC".
    pub last_podium: Vec<String>,
    /// ("VER", 331)
    pub standings: Vec<(String, f64)>,
}

#[derive(Serialize, Clone, Default)]
#[serde(rename_all = "camelCase")]
pub struct Quote {
    pub symbol: String,
    pub name: String,
    pub price: f64,
    pub change_pct: f64,
}

#[derive(Serialize, Clone, Default)]
#[serde(rename_all = "camelCase")]
pub struct Live {
    pub teams: Vec<Team>,
    pub f1: Option<F1>,
    pub markets: Vec<Quote>,
    pub trending: Vec<Quote>,
    pub crypto_trending: Vec<Quote>,
    pub errors: Vec<String>,
    /// When read, Unix ms.
    pub at: i64,
}

#[derive(Default)]
pub struct LiveState {
    data: Mutex<Live>,
    morocco_id: Mutex<Option<String>>,
}

fn now_ms() -> i64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis() as i64)
        .unwrap_or(0)
}

fn client() -> reqwest::Client {
    reqwest::Client::builder()
        .timeout(Duration::from_secs(12))
        .user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) Putshi")
        .build()
        .unwrap_or_default()
}

async fn get(c: &reqwest::Client, url: &str) -> Result<Value, String> {
    let resp = c.get(url).send().await.map_err(|e| e.to_string())?;
    if !resp.status().is_success() {
        return Err(format!("{} from {}", resp.status(), url.split('/').nth(2).unwrap_or(url)));
    }
    resp.json().await.map_err(|e| e.to_string())
}

// ── Football (ESPN) ──────────────────────────────────────────────────────────

/// "2026-10-26T20:00Z" → Unix ms.
fn parse_iso(s: &str) -> Option<i64> {
    let s = s.trim_end_matches('Z');
    let (date, time) = s.split_once('T')?;
    let mut d = date.split('-').map(|x| x.parse::<i64>().ok());
    let (y, m, day) = (d.next()??, d.next()??, d.next()??);
    let mut t = time.split(':').map(|x| x.parse::<f64>().ok());
    let (hh, mm) = (t.next()?? as i64, t.next()?? as i64);
    let ss = t.next().flatten().unwrap_or(0.0) as i64;
    // Days from civil (Howard Hinnant).
    let y2 = if m <= 2 { y - 1 } else { y };
    let era = y2.div_euclid(400);
    let yoe = y2 - era * 400;
    let mp = (m + 9) % 12;
    let doy = (153 * mp + 2) / 5 + day - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    let days = era * 146097 + doe - 719468;
    Some(((days * 86400) + hh * 3600 + mm * 60 + ss) * 1000)
}

fn score_of(v: &Value) -> Option<u32> {
    match v.get("score")? {
        Value::String(s) => s.parse().ok(),
        Value::Object(o) => o
            .get("value")
            .and_then(Value::as_f64)
            .map(|f| f as u32)
            .or_else(|| o.get("displayValue").and_then(Value::as_str).and_then(|s| s.parse().ok())),
        Value::Number(n) => n.as_u64().map(|n| n as u32),
        _ => None,
    }
}

fn parse_event(e: &Value, competition: &str) -> Option<Match> {
    let comp = e.get("competitions")?.get(0)?;
    let teams = comp.get("competitors")?.as_array()?;
    let side = |which: &str| teams.iter().find(|t| t.get("homeAway").and_then(Value::as_str) == Some(which));
    let (home, away) = (side("home")?, side("away")?);
    let name = |t: &Value| {
        t.pointer("/team/shortDisplayName")
            .or_else(|| t.pointer("/team/displayName"))
            .and_then(Value::as_str)
            .unwrap_or("?")
            .to_string()
    };
    let status = comp.get("status").or_else(|| e.get("status"))?;
    let state = status.pointer("/type/state").and_then(Value::as_str).unwrap_or("pre").to_string();
    let detail = status
        .pointer("/type/shortDetail")
        .or_else(|| status.get("displayClock"))
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string();
    let start_ms = e.get("date").and_then(Value::as_str).and_then(parse_iso).unwrap_or(0);
    let competition = e
        .pointer("/league/abbreviation")
        .or_else(|| e.pointer("/season/displayName"))
        .and_then(Value::as_str)
        .map(str::to_string)
        .unwrap_or_else(|| competition.to_string());
    let (hs, as_) = if state == "pre" { (None, None) } else { (score_of(home), score_of(away)) };
    Some(Match { competition, home: name(home), away: name(away), home_score: hs, away_score: as_, state, detail, start_ms })
}

fn league_label(lg: &str) -> &'static str {
    match lg {
        "esp.1" => "LaLiga",
        "uefa.champions" => "Champions League",
        "esp.copa_del_rey" => "Copa del Rey",
        "esp.super_cup" => "Supercopa",
        "fifa.world" => "World Cup",
        "fifa.worldq.caf" => "WC qualifier",
        "caf.nations" => "AFCON",
        "caf.nations_qual" => "AFCON qualifier",
        "fifa.friendly" => "Friendly",
        _ => "Football",
    }
}

async fn team(c: &reqwest::Client, name: &str, id: &str, leagues: &[&str]) -> Result<Team, String> {
    let mut all: Vec<Match> = Vec::new();
    let mut ok = false;
    for lg in leagues {
        for fixture in ["", "?fixture=true"] {
            let url = format!("https://site.api.espn.com/apis/site/v2/sports/soccer/{lg}/teams/{id}/schedule{fixture}");
            let Ok(v) = get(c, &url).await else { continue };
            ok = true;
            for e in v.get("events").and_then(Value::as_array).into_iter().flatten() {
                if let Some(m) = parse_event(e, league_label(lg)) {
                    if !all.iter().any(|x| x.start_ms == m.start_ms && x.home == m.home) {
                        all.push(m);
                    }
                }
            }
        }
    }
    if !ok {
        return Err(format!("{name}: scores unavailable"));
    }
    let now = now_ms();
    all.sort_by_key(|m| m.start_ms);
    let live = all.iter().find(|m| m.state == "in").cloned();
    let last = all.iter().rev().find(|m| m.state == "post" && m.start_ms <= now).cloned();
    let next = all.iter().find(|m| m.state == "pre" && m.start_ms >= now - 3 * 3600_000).cloned();
    Ok(Team { name: name.to_string(), live, last, next })
}

/// ESPN's id for Morocco's national team, from a competition's team list.
async fn morocco_id(app: &AppHandle, c: &reqwest::Client) -> Option<String> {
    if let Some(id) = app.state::<LiveState>().morocco_id.lock().unwrap().clone() {
        return Some(id);
    }
    for lg in ["fifa.world", "fifa.worldq.caf", "caf.nations", "fifa.friendly"] {
        let url = format!("https://site.api.espn.com/apis/site/v2/sports/soccer/{lg}/teams");
        let Ok(v) = get(c, &url).await else { continue };
        let teams = v.pointer("/sports/0/leagues/0/teams").and_then(Value::as_array).cloned().unwrap_or_default();
        for t in teams {
            let team = t.get("team").unwrap_or(&t);
            if team.get("displayName").and_then(Value::as_str) == Some("Morocco") {
                if let Some(id) = team.get("id").and_then(Value::as_str) {
                    *app.state::<LiveState>().morocco_id.lock().unwrap() = Some(id.to_string());
                    return Some(id.to_string());
                }
            }
        }
    }
    None
}

// ── Formula 1 (Jolpica) ──────────────────────────────────────────────────────

async fn f1(c: &reqwest::Client) -> Result<F1, String> {
    let base = "https://api.jolpi.ca/ergast/f1";
    let mut out = F1::default();
    if let Ok(v) = get(c, &format!("{base}/current/next.json")).await {
        if let Some(r) = v.pointer("/MRData/RaceTable/Races/0") {
            out.next_race = r.get("raceName").and_then(Value::as_str).map(str::to_string);
            out.next_place = r.pointer("/Circuit/Location/locality").and_then(Value::as_str).map(str::to_string);
            let date = r.get("date").and_then(Value::as_str).unwrap_or("");
            let time = r.get("time").and_then(Value::as_str).unwrap_or("12:00:00Z");
            out.next_ms = parse_iso(&format!("{date}T{time}"));
        }
    }
    if let Ok(v) = get(c, &format!("{base}/current/last/results.json")).await {
        if let Some(r) = v.pointer("/MRData/RaceTable/Races/0") {
            out.last_race = r.get("raceName").and_then(Value::as_str).map(str::to_string);
            out.last_podium = r
                .get("Results")
                .and_then(Value::as_array)
                .map(|a| {
                    a.iter()
                        .take(3)
                        .filter_map(|x| x.pointer("/Driver/code").or_else(|| x.pointer("/Driver/familyName")).and_then(Value::as_str))
                        .map(str::to_string)
                        .collect()
                })
                .unwrap_or_default();
        }
    }
    if let Ok(v) = get(c, &format!("{base}/current/driverStandings.json")).await {
        if let Some(list) = v.pointer("/MRData/StandingsTable/StandingsLists/0/DriverStandings").and_then(Value::as_array) {
            out.standings = list
                .iter()
                .take(3)
                .filter_map(|d| {
                    let code = d.pointer("/Driver/code").or_else(|| d.pointer("/Driver/familyName")).and_then(Value::as_str)?;
                    let pts = d.get("points").and_then(Value::as_str).and_then(|p| p.parse().ok()).unwrap_or(0.0);
                    Some((code.to_string(), pts))
                })
                .collect();
        }
    }
    if out.next_race.is_none() && out.last_race.is_none() {
        return Err("F1: unavailable".into());
    }
    Ok(out)
}

// ── Markets (Yahoo Finance, CoinGecko) ───────────────────────────────────────

async fn yahoo_quote(c: &reqwest::Client, symbol: &str, name: &str) -> Option<Quote> {
    let url = format!(
        "https://query1.finance.yahoo.com/v8/finance/chart/{}?range=1d&interval=1d",
        symbol.replace('^', "%5E")
    );
    let v = get(c, &url).await.ok()?;
    let meta = v.pointer("/chart/result/0/meta")?;
    let price = meta.get("regularMarketPrice")?.as_f64()?;
    let prev = meta.get("chartPreviousClose").or_else(|| meta.get("previousClose"))?.as_f64()?;
    let name = if name.is_empty() {
        meta.get("shortName").or_else(|| meta.get("longName")).and_then(Value::as_str).unwrap_or(symbol).to_string()
    } else {
        name.to_string()
    };
    Some(Quote { symbol: symbol.to_string(), name, price, change_pct: if prev > 0.0 { (price / prev - 1.0) * 100.0 } else { 0.0 } })
}

async fn markets(c: &reqwest::Client) -> (Vec<Quote>, Vec<Quote>, Vec<Quote>) {
    let mut main = Vec::new();
    for (s, n) in [("^GSPC", "S&P 500"), ("^IXIC", "Nasdaq"), ("BTC-USD", "Bitcoin"), ("ETH-USD", "Ethereum"), ("EURMAD=X", "EUR/MAD")] {
        if let Some(q) = yahoo_quote(c, s, n).await {
            main.push(q);
        }
    }
    // What people are looking at today.
    let mut trending = Vec::new();
    if let Ok(v) = get(c, "https://query1.finance.yahoo.com/v1/finance/trending/US?count=8").await {
        let symbols: Vec<String> = v
            .pointer("/finance/result/0/quotes")
            .and_then(Value::as_array)
            .map(|a| a.iter().filter_map(|q| q.get("symbol").and_then(Value::as_str)).map(str::to_string).collect())
            .unwrap_or_default();
        for s in symbols.iter().filter(|s| !s.starts_with('^')).take(5) {
            if let Some(q) = yahoo_quote(c, s, "").await {
                trending.push(q);
            }
        }
    }
    let mut crypto = Vec::new();
    if let Ok(v) = get(c, "https://api.coingecko.com/api/v3/search/trending").await {
        for coin in v.get("coins").and_then(Value::as_array).into_iter().flatten().take(4) {
            let item = coin.get("item").unwrap_or(coin);
            let symbol = item.get("symbol").and_then(Value::as_str).unwrap_or("").to_uppercase();
            let name = item.get("name").and_then(Value::as_str).unwrap_or("").to_string();
            let price = item.pointer("/data/price").and_then(Value::as_f64).unwrap_or(0.0);
            let change = item.pointer("/data/price_change_percentage_24h/usd").and_then(Value::as_f64).unwrap_or(0.0);
            if !symbol.is_empty() {
                crypto.push(Quote { symbol, name, price, change_pct: change });
            }
        }
    }
    (main, trending, crypto)
}

// ── Refresh loop ─────────────────────────────────────────────────────────────

pub async fn refresh(app: &AppHandle) -> Live {
    let c = client();
    let mut live = Live { at: now_ms(), ..Default::default() };
    match team(&c, "Barça", BARCA, BARCA_LEAGUES).await {
        Ok(t) => live.teams.push(t),
        Err(e) => live.errors.push(e),
    }
    match morocco_id(app, &c).await {
        Some(id) => match team(&c, "Morocco", &id, MOROCCO_LEAGUES).await {
            Ok(t) => live.teams.push(t),
            Err(e) => live.errors.push(e),
        },
        None => live.errors.push("Morocco: scores unavailable".into()),
    }
    match f1(&c).await {
        Ok(f) => live.f1 = Some(f),
        Err(e) => live.errors.push(e),
    }
    let (main, trending, crypto) = markets(&c).await;
    if main.is_empty() {
        live.errors.push("Markets: unavailable".into());
    }
    live.markets = main;
    live.trending = trending;
    live.crypto_trending = crypto;
    live
}

pub fn current(app: &AppHandle) -> Live {
    app.state::<LiveState>().data.lock().unwrap().clone()
}

pub fn start(app: AppHandle) {
    tauri::async_runtime::spawn(async move {
        let mut last_full = Instant::now() - Duration::from_secs(3600);
        loop {
            let any_live = current(&app).teams.iter().any(|t| t.live.is_some());
            let soon = current(&app)
                .teams
                .iter()
                .filter_map(|t| t.next.as_ref())
                .any(|m| (m.start_ms - now_ms()).abs() < 10 * 60_000);
            let every = if any_live || soon { Duration::from_secs(60) } else { Duration::from_secs(15 * 60) };
            if last_full.elapsed() >= every && !crate::integrations::PAUSED.load(std::sync::atomic::Ordering::Relaxed) {
                last_full = Instant::now();
                let fresh = refresh(&app).await;
                let old = current(&app);
                // Kick-off and goals for our teams (not on the first read).
                for t in &fresh.teams {
                    let Some(before) = old.teams.iter().find(|o| o.name == t.name) else { continue };
                    let Some(now) = &t.live else { continue };
                    let total = |m: &Match| m.home_score.unwrap_or(0) + m.away_score.unwrap_or(0);
                    let text = match &before.live {
                        None => format!("Kick-off: {} – {}", now.home, now.away),
                        Some(b) if total(now) > total(b) => format!(
                            "GOAL! {} {}–{} {} ({})",
                            now.home,
                            now.home_score.unwrap_or(0),
                            now.away_score.unwrap_or(0),
                            now.away,
                            now.detail
                        ),
                        Some(_) => continue,
                    };
                    let _ = app.emit("live-alert", &text);
                    crate::push::send(&app, "⚽ Putshi", &text);
                }
                *app.state::<LiveState>().data.lock().unwrap() = fresh;
                let _ = app.emit("live-changed", ());
            }
            tokio::time::sleep(Duration::from_secs(20)).await;
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn iso_dates() {
        assert_eq!(parse_iso("1970-01-01T00:00Z"), Some(0));
        assert_eq!(parse_iso("2026-10-26T20:00Z"), Some(1_793_044_800_000));
        assert_eq!(parse_iso("2026-03-08T04:00:00Z"), Some(1_772_942_400_000));
    }

    #[test]
    fn espn_event() {
        let e: Value = serde_json::from_str(r#"{"date":"2026-10-26T20:00Z","league":{"abbreviation":"LaLiga"},
          "competitions":[{"competitors":[
            {"homeAway":"home","team":{"shortDisplayName":"Barcelona"},"score":{"value":2.0,"displayValue":"2"}},
            {"homeAway":"away","team":{"shortDisplayName":"Real Madrid"},"score":"1"}],
            "status":{"type":{"state":"in","shortDetail":"67'"}}}]}"#).unwrap();
        let m = parse_event(&e, "x").unwrap();
        assert_eq!((m.home.as_str(), m.away.as_str(), m.home_score, m.away_score), ("Barcelona", "Real Madrid", Some(2), Some(1)));
        assert_eq!((m.state.as_str(), m.detail.as_str(), m.competition.as_str()), ("in", "67'", "LaLiga"));
    }
}
