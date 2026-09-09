# HANDOFF — Seeker Gravity (ROTA reskin for the Solana Seeker dApp Store)

Continue this in a fresh conversation. Everything below is on disk.

## What this is
**Seeker Gravity** = Harmony Monroe's MIT-licensed Godot 3.6 puzzle-platformer **ROTA: Bend Gravity**
(github.com/HarmonyHoney/ROTA, branch master4, Steam Very Positive) rebranded for the Seeker store.
Package `com.justinliehu.seekergravity`, version 1.0.0 (1). Submission guide: **`SEEKER-SUBMIT.md`**.

## Paths
- Project: `C:\Users\justi\Desktop\games\rota\` (depth-1 clone; origin = the AUTHOR's repo — never push there)
- **Godot 3.6.1** editor: `C:\Users\justi\godot3\Godot_v3.6.1-stable_win64.exe`
  templates: `C:\Users\justi\godot3\templates\templates\` · debug keystore: `C:\Users\justi\godot3\keys\debug.keystore`
- Android build-tools: `C:\Users\justi\AppData\Local\Android\Sdk\build-tools\35.0.0\`
- Brand pipeline: `tools\brand\make_gravity_brand.py` (wordmark/icons/splash/store art), `tools\brand\reskin.py`
  (idempotent edits + deletions + leftover-string audit), `tools\brand\capture_title.gd` (Godot 3 screenshot harness;
  run WITHOUT --no-window), `tools\brand\new-release-key.ps1`, `tools\brand\build-release.ps1`
- Store: `store-assets\` (icon/banner/feature, `screenshots\` title+world1+world3+world3a at 1920×1080, `config.reference.yaml`)
- Website: **lives in `heli\web\`** (one Koyeb service serves both games) → `/gravity/`, `/gravity/download`,
  `/gravity/legal/{privacy,terms,license}`, assets in `heli\web\static-gravity\`. Push `heli\web` = auto-redeploy.
  Live: https://seeker-heli-seeker-doudizhu-126cd50d.koyeb.app/gravity/

## DONE + verified (2026-09-04)
- Steam stripped (addon + autoload + stubs in `src/autoload/Shared.gd`), itch/Flatpak files removed, unused fonts removed.
- Rebranded: `project.godot`, Android preset (prebuilt template, arm64 only, no author keystore), `MenuTitle.tscn`
  (title sprite = our wordmark, "BASED ON ROTA" line, credits mark "ROTA by Harmony Monroe"), `Splash.tscn`.
- `build\android\seeker-gravity-debug.apk` 54 MB, arm64, targetSdk 34, **zero permissions**, no author strings inside.
- Site tested (TestClient) and deployed; heli's existing URLs untouched.
- User is messaging the author on Bluesky (@harmonymonroe.bsky.social) as a courtesy (MIT does not require it).

## TODO (user)
1. Copy Godot 3 templates + debug keystore into their own %APPDATA% (one-liner in SEEKER-SUBMIT.md §1).
2. `new-release-key.ps1` → `build-release.ps1` (debug-key export, then apksigner re-sign with their key).
3. Sideload-test on the Seeker. 4. Portal: Add a dApp → New Version → review notes → submit.

## Gotchas
- Godot 3 preset: with `custom_build/use_custom_build=false` the `custom_build/target_sdk` must be "" or export refuses.
- `project.godot` kept a `Steam` autoload line after deleting the addon → "Can't autoload" until removed.
- Loading level .tscn files standalone renders only sky (no player/camera); hub scenes (`0_hub.tscn`) render fully —
  worlds 1/3/3A good, 2/2A/2B/2C/3B show only the player.
- Python heredocs in this environment mangle backslashes; write files with the Write tool.
- The sandbox's %APPDATA% is virtual: anything installed there exists only for Claude, not for the user.
