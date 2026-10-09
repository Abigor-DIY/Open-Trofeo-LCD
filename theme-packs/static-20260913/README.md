# Static theme pack — installed in the source and active gallery

Integration completed after the backend optimization build `fps1`: the active
gallery now contains eight themes. Heritage Duality and Wolfstorm Forge were
moved to `.codex-backups/20260914-theme-gallery/` (source and runtime copies).
The optimized backend was not replaced. Existing DEB files were not rebuilt;
the next package build must include the updated source theme inventory.

Three 1920x462 themes with 180-degree LCD rotation:

- Amber Hi-Fi: media, live EQ visualization, weather and system summary.
- Nordic Forecast: current weather, seven-day forecast and system summary.
- Crimson Telemetry: FPS, frame time, min/avg/max, load gauges and process RSS.

All backgrounds are static; weather-icon animation and media marquee are off.
Live data and EQ can still refresh. PNG previews use synthetic data and do not
represent hardware measurements. JSON themes use real runtime stat sources.

## Integration after the other agent's backend work

No backend files or runtime configuration were changed by this pack.
No application restart or USB test was performed during concurrent work.

1. Back up source and installed theme registries and the two retired JSON files.
2. Add the three JSON files to the source and active workdir themes directories.
3. Retire only `themes/heritage_duality.json` (Heritage Duality) and
   `themes/wolfstorm_forge.json` (Wolfstorm Forge) from the gallery and active
   source theme scan. Move them to an archive outside `themes/`, do not destroy.
4. Keep Orbital Relay as the only enabled background animation. Preserve
   Neon Frame Arena, Obsidian Pulse, Verdant Bloom and Valhalla Command.
5. Check startup/playlist references before removing registry entries. Observed
   user settings: startup Orbital Relay; automatic gaming Valhalla Command.
6. Update release theme inventory (expected total: eight) and documentation.
   Do not delete asset folders without checking shared references; animated
   motifs may share assets with other themes.
7. Run offline theme/schema/render tests, then verify gallery and USB switching
   on hardware only after the backend agent's work is ready.

The checklist above records the integration procedure. Offline schema/render
and release checks passed with eight themes at integration time.
