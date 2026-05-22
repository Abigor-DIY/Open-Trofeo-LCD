# Game / FPS Widgets

Open Trofeo LCD can detect likely game processes from `/proc` without extra
software. Live FPS values need MangoHud logging enabled for the running game.

Recommended Ubuntu packages:

```bash
sudo apt install mangohud
```

Optional GUI for editing MangoHud config:

```bash
sudo apt install goverlay
```

Minimal MangoHud config for Open Trofeo LCD:

```ini
fps
frametime
autostart_log=1
log_interval=100
output_folder=~/.local/state/open-trofeo-lcd/mangohud
```

For a Steam game, set launch options to:

```text
mangohud %command%
```

For gamescope sessions, use mangoapp instead:

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
