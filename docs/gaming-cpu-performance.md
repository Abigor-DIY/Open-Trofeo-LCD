# Automatic gaming power profile

Configuration → gaming/FPS includes **Profil CPU performance po wykryciu gry**.
This is opt-in, saved as `gaming_cpu_performance` in the GUI state.

The desktop GUI requests a temporary `performance` hold from
`power-profiles-daemon` through `powerprofilesctl launch`. It does not write CPU
sysfs, change Steam options, or require the entire application to run as root.
The service must expose the performance profile and authorize the current user.
Failures appear under the checkbox; toggle it off/on to retry. There is no
automatic sudo/polkit policy installation.

Game detection is shared with automatic themes, but independent of the selected
theme and FPS samples. A detected game ending has a 12-second grace period;
missing valid backend game status releases the hold after 30 seconds. Startup
times out after 10 seconds. Disabling the option or quitting releases the hold;
hiding in the tray keeps automation active. The helper exits on stdin EOF if the
GUI dies. The daemon then manages the effective profile, including other clients
and user changes, rather than Trofeo forcing a saved profile over them.

The UI reports an accepted request, not a guarantee of CPU frequency, effective
profile under all thermal/power restrictions, or additional FPS.
