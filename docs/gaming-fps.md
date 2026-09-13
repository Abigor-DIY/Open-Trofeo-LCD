# Game / FPS Widgets

Open Trofeo LCD can detect likely game processes from `/proc` without extra
software. Live FPS values should come from the Open Trofeo FPS probe so the game
screen stays clean and the metrics are rendered only on the Trofeo LCD.

Optional fallback Ubuntu packages:

```bash
sudo apt install mangohud
```

Optional GUI for editing MangoHud config:

```bash
sudo apt install goverlay
```

MangoHud log reading is disabled by default. Enable it only as a fallback:

```bash
OPEN_TROFEO_MANGOHUD_FALLBACK=1
```

The preferred path is documented in `docs/gaming-fps-probe.md`. The current
native prototype for Vulkan games is:

```text
OPEN_TROFEO_FPS_LAYER=1 OPEN_TROFEO_FPS_SOCKET=/run/user/$UID/open-trofeo-lcd/fps.sock OPEN_TROFEO_GAME_NAME="Game Name" OPEN_TROFEO_GAME_LAUNCHER=Steam %command%
```

The app also shows a shorter copy-ready version in `Configuration > Gaming FPS`:

```bash
OPEN_TROFEO_FPS_LAYER=1 OPEN_TROFEO_GAME_NAME="Game Name" OPEN_TROFEO_GAME_LAUNCHER=Steam %command%
```

Replace `Game Name` with the title you want shown on the Trofeo LCD.

## Session history and CSV logs

Every session received from the Open Trofeo FPS probe is logged automatically to:

```text
~/.local/state/open-trofeo-lcd/fps-sessions/YYYY-MM-DD/
```

The CSV contains timestamps, FPS, frame time, session AVG/MIN/MAX, rolling
1%/0.1% lows, stutter samples and the native frame counter. Logging runs on a
separate bounded worker queue, so a slow disk cannot block the FPS socket or LCD
rendering. The current CSV path and a live/last-session summary are visible in
`Configuration > Gaming FPS`.

AVG, MIN, MAX, average/max frame time and stutter count cover the current probe
session. The 1% and 0.1% lows use the most recent 60 seconds, keeping their
calculation bounded during long gaming sessions. A new process ID or a gap over
eight seconds starts a new session and a new CSV file.

## Automatic gaming theme

`Configuration > Gaming FPS` can switch the LCD to a selected theme when a game
is detected. Enable `Switch to selected theme when a game is detected`, then
choose the theme from the combo box below it.

The return theme is not configured separately. Open Trofeo LCD remembers the
theme that was active immediately before the game was detected and restores it
after the game exits. This allows normal daily/static themes to remain flexible.

There is also a test option:

```text
Experimental: restore previous theme when FPS disappears
```

Use it when minimized games keep the game process alive but stop reporting FPS
and frame time. After the configured `FPS loss delay`, the app restores the
previous theme. When FPS or frame time returns, the app switches back to the
selected gaming theme. This option is intentionally marked experimental because
different games, Proton versions and compositors can pause FPS reporting for
short periods during startup, loading screens or alt-tab transitions.

Recommended initial value:

```text
FPS loss delay: 12 s
```

## Valhalla Command gaming theme

The bundled 1920x462 theme shows FPS/session statistics, GPU/CPU/RAM/VRAM
gauges, recent FPS and frametime graphs, temperatures, and the four processes
with highest RSS. RSS is resident memory in GiB per PID, not an application-tree
total; shared pages may appear in multiple processes. The process ranking is
read asynchronously from /proc at most every three seconds. Inaccessible or
exited processes are skipped. Missing readings display N/A. Graphs accumulate
recent render samples, not individual game frames; lows are probe-sample lows.

## KDE Wayland VRR buttons

The Gaming FPS configuration card also shows the current VRR policy for every
VRR-capable KScreen output and provides three one-click policies:

- `Automatic` (recommended): VRR remains available to suitable full-screen
  games without being forced on the Plasma desktop.
- `Always`: force VRR continuously. Some displays can flicker on the desktop in
  this mode.
- `Off`: disable VRR (`Never`).

The buttons call `scripts/trofeo_vrr.sh`. The helper can also be used directly:

```bash
scripts/trofeo_vrr.sh status
scripts/trofeo_vrr.sh automatic
scripts/trofeo_vrr.sh always
scripts/trofeo_vrr.sh never
```

Increase the delay if the LCD switches too early during game startup or loading
screens. The restore-on-FPS-loss path only restores automatically while the
currently active theme is still the selected gaming theme, so a manual theme
change during a game is less likely to be overwritten.

TODO before public release:

- Document how Open Trofeo launch options should coexist with other game tools
  and overlays, for example MangoHud, Gamescope, OBS helpers, Proton flags and
  game-specific environment variables.
- Check practical Steam launch option length limits and provide a shorter
  wrapper command if long environment-variable chains become fragile.
- Add tested examples for non-Steam games: Lutris, Heroic, Bottles, native
  desktop shortcuts and direct terminal launches.

For Steam Flatpak, install the layer and allow Steam to reach the backend socket:

```bash
scripts/install_fps_layer_user.sh
# or repair only the Flatpak permission:
scripts/configure_steam_flatpak_fps.sh
```

The helper applies:

```bash
flatpak override --user --filesystem=xdg-run/open-trofeo-lcd com.valvesoftware.Steam
```

Restart Steam after changing Flatpak overrides. Steam installed from a DEB
package does not need this Flatpak permission step.

If the Vulkan layer is not installed or a game bypasses it, direct preload can
also be tested:

```text
LD_PRELOAD=/home/abigor/Workspace/Open-Trofeo-LCD/native/fps_probe/libopen_trofeo_fps_probe.so OPEN_TROFEO_GAME_NAME="Game Name" OPEN_TROFEO_GAME_LAUNCHER=Steam %command%
```

If MangoHud fallback is used, a minimal config is:

```ini
fps
frametime
autostart_log=1
log_interval=100
output_folder=~/.local/state/open-trofeo-lcd/mangohud
```

For a Steam game with MangoHud fallback, set launch options to:

```text
mangohud %command%
```

For gamescope sessions with MangoHud fallback, use mangoapp instead:

```text
gamescope --mangoapp -- %command%
```

Theme sources exposed by the backend:

- `game_active`
- `game_name`
- `game_process`
- `game_launcher`
- `game_fps`
- `game_frametime_ms`
- `game_fps_source`
- `game_overlay`
