// Desktop info for the island's PC view and the compact notch: CPU, memory,
// system disk, network speed, battery, uptime. Sampled only when the island
// asks, so a hidden island costs nothing.

use std::sync::Mutex;
use std::time::Instant;

use serde::Serialize;
use sysinfo::{CpuRefreshKind, Disks, MemoryRefreshKind, Networks, RefreshKind, System};

#[derive(Serialize, Clone, Default)]
#[serde(rename_all = "camelCase")]
pub struct SystemStats {
    /// 0–100, all cores.
    pub cpu: f32,
    pub mem_used: u64,
    pub mem_total: u64,
    /// The disk Windows runs from (C:), or the root filesystem on Linux.
    pub disk_used: u64,
    pub disk_total: u64,
    /// Bytes per second since the previous sample.
    pub net_down: u64,
    pub net_up: u64,
    /// None on a desktop without a battery.
    pub battery: Option<u8>,
    pub charging: bool,
    pub uptime_secs: u64,
    pub host: String,
}

pub struct Sampler {
    sys: System,
    networks: Networks,
    last_net: Option<(Instant, u64, u64)>,
    /// Disk space barely moves and listing disks can be slow (network drives),
    /// so it is read once a minute.
    disk: Option<(Instant, u64, u64)>,
}

impl Default for Sampler {
    fn default() -> Self {
        let sys = System::new_with_specifics(
            RefreshKind::nothing()
                .with_cpu(CpuRefreshKind::nothing().with_cpu_usage())
                .with_memory(MemoryRefreshKind::nothing().with_ram()),
        );
        Self { sys, networks: Networks::new_with_refreshed_list(), last_net: None, disk: None }
    }
}

#[derive(Default)]
pub struct Stats(pub Mutex<Option<Sampler>>);

impl Stats {
    pub fn sample(&self) -> SystemStats {
        let mut guard = self.0.lock().unwrap();
        let s = guard.get_or_insert_with(Sampler::default);

        // CPU usage is the change since the previous refresh; the island asks
        // every couple of seconds, which is the interval it averages over.
        s.sys.refresh_cpu_usage();
        s.sys.refresh_memory();

        s.networks.refresh(true);
        let (rx, tx) = s
            .networks
            .values()
            .fold((0u64, 0u64), |(r, t), n| (r + n.total_received(), t + n.total_transmitted()));
        let now = Instant::now();
        let (net_down, net_up) = match s.last_net {
            Some((then, r0, t0)) => {
                let dt = now.duration_since(then).as_secs_f64().max(0.001);
                (
                    (rx.saturating_sub(r0) as f64 / dt) as u64,
                    (tx.saturating_sub(t0) as f64 / dt) as u64,
                )
            }
            None => (0, 0),
        };
        s.last_net = Some((now, rx, tx));

        let (disk_used, disk_total) = match s.disk {
            Some((at, used, total)) if now.duration_since(at).as_secs() < 60 => (used, total),
            _ => {
                let (used, total) = system_disk();
                s.disk = Some((now, used, total));
                (used, total)
            }
        };
        let (battery, charging) = battery();

        SystemStats {
            cpu: s.sys.global_cpu_usage().clamp(0.0, 100.0),
            mem_used: s.sys.used_memory(),
            mem_total: s.sys.total_memory(),
            disk_used,
            disk_total,
            net_down,
            net_up,
            battery,
            charging,
            uptime_secs: System::uptime(),
            host: System::host_name().unwrap_or_default(),
        }
    }
}

fn system_disk() -> (u64, u64) {
    let disks = Disks::new_with_refreshed_list();
    let target = if cfg!(windows) { "C:\\" } else { "/" };
    let disk = disks
        .list()
        .iter()
        .find(|d| d.mount_point().to_string_lossy().eq_ignore_ascii_case(target))
        .or_else(|| disks.list().iter().max_by_key(|d| d.total_space()));
    match disk {
        Some(d) => (d.total_space().saturating_sub(d.available_space()), d.total_space()),
        None => (0, 0),
    }
}

#[cfg(windows)]
fn battery() -> (Option<u8>, bool) {
    use windows::Win32::System::Power::{GetSystemPowerStatus, SYSTEM_POWER_STATUS};
    let mut status = SYSTEM_POWER_STATUS::default();
    if unsafe { GetSystemPowerStatus(&mut status) }.is_err() {
        return (None, false);
    }
    // BatteryFlag 128 = no system battery; 255 = unknown. Percent 255 = unknown.
    if status.BatteryFlag & 128 != 0 || status.BatteryFlag == 255 || status.BatteryLifePercent > 100 {
        return (None, false);
    }
    (Some(status.BatteryLifePercent), status.ACLineStatus == 1)
}

#[cfg(not(windows))]
fn battery() -> (Option<u8>, bool) {
    let Ok(entries) = std::fs::read_dir("/sys/class/power_supply") else {
        return (None, false);
    };
    for entry in entries.flatten() {
        let path = entry.path();
        let kind = std::fs::read_to_string(path.join("type")).unwrap_or_default();
        if kind.trim() != "Battery" {
            continue;
        }
        let Some(pct) = std::fs::read_to_string(path.join("capacity"))
            .ok()
            .and_then(|s| s.trim().parse::<u8>().ok())
        else {
            continue;
        };
        let status = std::fs::read_to_string(path.join("status")).unwrap_or_default();
        let charging = matches!(status.trim(), "Charging" | "Full");
        return (Some(pct.min(100)), charging);
    }
    (None, false)
}
