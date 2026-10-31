# TV memory measurement — 2026-10-31

Source: `tv-memory-report.json`, three samples 10:46:17–10:46:38 UTC. The foreground API identified `com.local.hdmihome` in all samples. No TV state was changed by the measurement.

| Metric | Observed |
|---|---:|
| RAM visible to Linux | 1982.9 MiB |
| Used (MemTotal minus MemAvailable) | 1462.1–1463.6 MiB |
| Available | 519.3–520.8 MiB |
| Logical swap used | 315.7–315.9 MiB |
| Dashboard-associated process PSS | 28.2 MiB |
| Dashboard-associated process RSS | 36.4–36.5 MiB |
| Dashboard-associated private resident memory | 22.6 MiB |

The dashboard-associated WebAppMgr process was PID 12498, identified by app ID in its arguments. PSS apportions shared mappings; RSS includes shared pages. Other WebAppMgr/shared services cannot be assigned solely to the dashboard by this report. Do not treat 28.2 MiB as a measured incremental cost of the entire dashboard stack.

Last sample's largest process was AppleTV PID 12710 at 167.7 MiB PSS (183.7 MiB RSS), still running while the dashboard was foreground. SDX PID 3348 was running at 8.9 MiB PSS. The measurement observer consumed 5.3 MiB PSS. All 198 scanned processes had PSS readings; no processes were skipped.

This is a current-session measurement, **not a clean boot baseline**: uptime was 60.8–61.2 minutes, and Apple TV was resident. RAM was steady across the short sampling window; that does not establish long-term leak behavior or debloat savings. Logical swap usage is not additional physical RAM usage and must not be added directly to the used-RAM figure.

To capture the requested boot baseline, fully reboot with Xbox off, wait around 90 seconds for startup cleanup, leave only the dashboard open and run `measure-tv-memory.ps1` before launching other apps. Save this report separately before rerunning if a comparison is wanted. Compare identical startup/app states.
