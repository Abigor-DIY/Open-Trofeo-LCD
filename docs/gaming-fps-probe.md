# Open Trofeo FPS Probe

Open Trofeo LCD exposes a local Unix datagram socket for headless game FPS data.
The goal is to show FPS and frame time on the Trofeo LCD without drawing an
overlay over the game.

## Socket

Default path:

```text
$XDG_RUNTIME_DIR/open-trofeo-lcd/fps.sock
```

Fallback when `XDG_RUNTIME_DIR` is not set:

```text
/run/user/$UID/open-trofeo-lcd/fps.sock
```

Override:

```bash
OPEN_TROFEO_FPS_SOCKET=/custom/path/fps.sock
```

## Datagram schema

Send UTF-8 JSON datagrams:

```json
{
  "fps": 144.0,
  "frametime_ms": 6.94,
  "source": "open-trofeo-vulkan-probe",
  "game_name": "Example Game",
  "game_process": "game.exe",
  "game_launcher": "Steam",
  "game_overlay": "none",
  "pid": 12345,
  "timestamp": 1779470000.0
}
```

The backend treats samples older than 2.5 seconds as stale. MangoHud log reading
is disabled by default and can be enabled only as an explicit fallback:

```bash
OPEN_TROFEO_MANGOHUD_FALLBACK=1
```

## Test sender

```bash
python3 scripts/trofeo_fps_probe_sender.py --fps 144 --duration 10 --game-name ProtonTest
```

Expected backend status:

```text
config.fps_probe.active = yes
config.game.game_fps = 144
config.game.game_fps_source = open-trofeo-test-probe
```

Accepted samples are also written asynchronously to one CSV file per probe
session under:

```text
~/.local/state/open-trofeo-lcd/fps-sessions/YYYY-MM-DD/
```

`config.fps_probe.log_path` reports the current or most recent file, while
`config.fps_probe.session` exposes the live or last-session summary used by the
GUI. Session AVG/MIN/MAX values are cumulative; 1% and 0.1% lows cover the most
recent 60 seconds.

## Native Vulkan preload probe

The first no-overlay native probe is a Vulkan helper. It does not draw anything
over the game. It only hooks `vkQueuePresentKHR`, calculates FPS and frame time,
and sends the result to the backend socket.

Build:

```bash
scripts/build_fps_probe.sh
```

### Vulkan layer mode

Install the opt-in layer manifest for the current user:

```bash
scripts/install_fps_layer_user.sh
```

Remove the user manifest:

```bash
scripts/uninstall_fps_layer_user.sh
```

Steam launch option example:

```bash
OPEN_TROFEO_FPS_LAYER=1 OPEN_TROFEO_FPS_SOCKET=/run/user/$UID/open-trofeo-lcd/fps.sock OPEN_TROFEO_GAME_NAME="Game Name" OPEN_TROFEO_GAME_LAUNCHER=Steam %command%
```

The GUI exposes a copy-ready launch option in Configuration > Gaming FPS:

```bash
OPEN_TROFEO_FPS_LAYER=1 OPEN_TROFEO_GAME_NAME="Game Name" OPEN_TROFEO_GAME_LAUNCHER=Steam %command%
```

Use the per-game Steam Properties > Launch Options field and replace `Game Name`.

The layer manifest is opt-in. It is only enabled when `OPEN_TROFEO_FPS_LAYER=1`
is present in the launched process. When Flatpak Steam is installed,
`scripts/install_fps_layer_user.sh` also installs a manifest under
`~/.var/app/com.valvesoftware.Steam/.local/share/vulkan/implicit_layer.d` because
Steam Runtime/pressure-vessel can strip `VK_ADD_IMPLICIT_LAYER_PATH`.

For Steam Flatpak, the game also needs access to the backend socket under
`$XDG_RUNTIME_DIR/open-trofeo-lcd`. The installer applies this narrow user-level
override automatically:

```bash
flatpak override --user --filesystem=xdg-run/open-trofeo-lcd com.valvesoftware.Steam
```

If the game starts but the widget keeps showing `open-trofeo-probe-waiting` or
`N/A`, run the helper and restart Steam completely:

```bash
scripts/configure_steam_flatpak_fps.sh
```

Steam installed from a DEB package does not need the Flatpak override. Keep the
same launch option; the socket path is already visible to normal host processes.

## Minimized games and auto-theme restore

Some games stop presenting frames when minimized or alt-tabbed. In that state the
process may still be detected as a game, but the probe reports no fresh FPS or
frame time. The GUI has an experimental option in `Configuration > Gaming FPS`:

```text
Experimental: restore previous theme when FPS disappears
```

When enabled, Open Trofeo LCD waits for the configured `FPS loss delay`, restores
the theme that was active before the game, and switches back to the selected
gaming theme after fresh FPS or frame-time data returns. Start testing with
`12 s`; raise it for games with long loading screens or unstable startup FPS
reporting.

Temporary test without installing the manifest:

```bash
OPEN_TROFEO_FPS_LAYER=1 VK_IMPLICIT_LAYER_PATH=/home/abigor/Workspace/Open-Trofeo-LCD/native/fps_probe/implicit_layer.d vulkaninfo --summary
```

### LD_PRELOAD mode

If layer discovery does not work for a game, use direct preload:

```bash
LD_PRELOAD=/home/abigor/Workspace/Open-Trofeo-LCD/native/fps_probe/libopen_trofeo_fps_probe.so OPEN_TROFEO_GAME_NAME="Game Name" OPEN_TROFEO_GAME_LAUNCHER=Steam %command%
```

Optional custom socket path:

```bash
OPEN_TROFEO_FPS_SOCKET=/run/user/$UID/open-trofeo-lcd/fps.sock
```

This is still a prototype path for quick testing. It should work with Vulkan
games that resolve `vkQueuePresentKHR` through the normal loader path. If a game
or compatibility layer bypasses that path, the backend will simply keep showing
`open-trofeo-probe-waiting` instead of FPS.

The probe writes diagnostics to:

```text
~/.local/state/open-trofeo-lcd/fps-probe.log
```

Useful markers are `loaded`, `negotiate`, `create-instance`, `create-device`,
and `first-present`. When these entries appear but the backend still waits for
samples, check the socket path and Flatpak permission first.

## FPS and display support report

If the game runs but the Trofeo shows `N/A`, collect the report while the game
is presenting frames. From a terminal, run:

```bash
python3 /usr/share/open-trofeo-lcd/scripts/trofeo_support_report.py --game Enshrouded --delay 15
```

Switch back into the unpaused game during those 15 seconds. The tool saves
`~/trofeo-support.txt`. Review it, then attach it to the support conversation.
Source users can run `python3 scripts/trofeo_support_report.py` with the same
options. `--url http://127.0.0.1:18777` can select a different local backend port.

The report checks the backend FPS snapshot, both native/Flatpak manifests and
their libraries, the matching game's loaded probe/MangoHud libraries, socket
visibility inside the game's namespace, selected FPS environment variables,
probe log markers and display-worker errors. It also reports installed TRCC
versions and saved Trofeo orientation. It does not touch USB, send synthetic
FPS samples, change settings, upload data, or export weather coordinates/full
process environments. Home and runtime paths are replaced with placeholders.

`OPEN_TROFEO_FPS_LAYER=1` opts into an installed layer; the flag alone does not
install it. If the report says the manifest/library is missing, use
**Configuration → Gaming FPS → Configure FPS layer**, restart Steam completely
and retry. MangoHud's visible FPS counter does not establish that the separate
Open Trofeo layer has loaded. Compare its `loaded`, `create-device`,
`first-present` and `socket-error` markers before changing launch options.

## Native probe plan

The production probe should use the same socket and schema:

- Vulkan implicit layer: expand dispatch-chain handling if some Proton titles
  bypass the prototype path.
- OpenGL preload helper: hook `glXSwapBuffers` and `eglSwapBuffers`.
- Steam launch option: set environment for the game process without enabling an
  on-screen overlay.
