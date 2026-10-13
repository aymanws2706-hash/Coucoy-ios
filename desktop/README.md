# Desktop (personal build of Coucou for Windows)

The Windows app is [Coucou](https://github.com/Louis-CFM/coucou) (MIT) built at
the commit pinned in `.github/workflows/coucou-windows.yml`, with the files in
`overlay/` copied over it before the build. Each overlay file is either new or a
full copy of Coucou's file with these changes:

| File | Change |
|---|---|
| `src-tauri/src/sysstats.rs` | New. CPU, memory, disk C:, network speed, battery, uptime. |
| `src-tauri/src/lib.rs` | `system_stats` command; settings window re-centres when opened. |
| `src-tauri/Cargo.toml` | `sysinfo`, and the Windows power API for the battery. |
| `src/views/pc.ts`, `pc.css` | New. The "This PC" panel and the notch readout. |
| `src/views/views.ts`, `icons.ts` | "This PC" tab (chip icon) in the header. |
| `src/island/island.ts` | Notch shows clock · CPU · battery; stats sampled every 2 s. |
| `src/island/fsm.ts` | The notch never hides. |
| `src/core/state.ts` | Opens on "This PC"; no integrations switched on by default. |
| `src/core/layout.ts`, `bridge.ts` | `pc` view size, wider notch, `systemStats()`. |

When moving to a newer Coucou commit, re-copy those upstream files and re-apply
the changes above.

Push to `main` with a change under `desktop/` and GitHub builds the installer
into the **coucou-windows** release.
