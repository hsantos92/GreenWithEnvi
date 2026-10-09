# GreenWithEnvi (GWE)

GreenWithEnvi is a GTK 3 utility for monitoring and controlling NVIDIA GPUs on
Linux. This fork uses NVML for modern NVIDIA drivers on Wayland and X11.

Project: [hsantos92/GreenWithEnvi](https://github.com/hsantos92/GreenWithEnvi)

## Features

- GPU temperature, utilization, memory, power, clocks, fan duty and RPM readings.
- Saved fan curves with interpolation and cooling hysteresis.
- GPU and memory clock-offset profiles and power-limit controls.
- Historical graphs and an optional app indicator.
- Authentication through polkit for controls; the desktop app runs as your user.

Available readings and controls depend on the GPU and driver. Unsupported sensors
remain blank. Coolbits and the X11 NV-CONTROL extension are no longer required.
<img width="3389" height="1412" alt="Screenshot From 2026-10-08 23-12-29" src="https://github.com/user-attachments/assets/ab305e71-da9c-4f56-a0ba-9bb640bd0155" />

## Run from source

Clone the `master` branch:

```sh
git clone --branch master https://github.com/hsantos92/GreenWithEnvi.git
cd GreenWithEnvi
python3 -m venv --system-site-packages ~/.cache/gwe-dev
~/.cache/gwe-dev/bin/pip install -r requirements.txt
GWE_PYTHON=~/.cache/gwe-dev/bin/python bash scripts/run-native.sh
```

Install the native dependencies first; see [NVML-MIGRATION.md](NVML-MIGRATION.md)
for requirements, authorization behavior and validation commands. The launcher
builds resources and runs this checkout without a system-wide install.

The inherited Flatpak packaging has not been migrated or validated for this
backend, and controls are disabled inside Flatpak. Existing Flathub and distro
packages should not be assumed to contain this fork's changes.

## Profiles and controls

Select a fan profile and click **Apply** to evaluate it immediately. Cooling
hysteresis accumulates from the last duty change; rising duty is applied
immediately. The graph uses the saved curve endpoints, and requested fan duty is
clamped to the driver's supported range. **Auto** restores firmware fan control.

Existing profiles are reused from `$XDG_CONFIG_HOME/gwe/gwe.db`, normally
`~/.config/gwe/gwe.db`. The `gwe` package name and `com.leinardi.gwe` application
ID remain for compatibility with existing settings and resources. This branding
change does not migrate or overwrite profiles.

Memory offsets use the original GWE MHz units; NVML receives twice that value
as a memory transfer-rate offset. Clock offsets and power limits are not
reset automatically when the app exits. See the migration notes for the fan
worker's disconnect and timeout restoration behavior.

## Start at login

Enable launch on login in Preferences, or run the native launcher with
`--autostart-on`. Native startup entries use the checkout launcher and its
Python environment, so they do not require a system-installed `gwe` command.
Toggle the preference off and on to refresh an older startup entry.

The app starts hidden as your normal user. Applying a saved custom fan profile
requires polkit authentication unless the optional system helper is installed.
See [CONTROL-HELPER.md](CONTROL-HELPER.md) for passwordless authorization scoped
to your active local session. Keep the app running to follow the curve; quitting
restores firmware fan control.

The main window remembers its normal size and maximized state across launches.
Primary activation opens or raises the window; middle-click toggles its visibility
and right-click opens its menu.
Your desktop chooses the activation gesture: GNOME's AppIndicator extension uses
double-click or middle-click, while other hosts may use a single click. The tray
requires the `Dbusmenu` and `DbusmenuGtk3` GObject introspection libraries.

For single-click opening and double-click hiding on GNOME, apply the optional
GWE-specific AppIndicator patch from the checkout root:

```sh
patch --backup --forward --directory="$HOME/.local/share/gnome-shell/extensions/appindicatorsupport@rgcjonas.gmail.com" -p1 < contrib/gnome-appindicator-gwe.patch
```

Log out and back in to load it. A single left-click opens or raises GWE, a double
left-click hides its window while GPU controls keep running, and right-click
opens the menu. The patch also fixes double-click settings lookup on GNOME 51.
It targets a user-installed AppIndicator extension and saves the original as
`indicatorStatusIcon.js.orig`; extension updates may require reapplying it.
If patch reports that it is already applied or its context does not match, stop
and inspect the installed extension before retrying.


## Command-line options

| Option | Description |
| --- | --- |
| `-v`, `--version` | Show the version |
| `--debug` | Enable debug logging |
| `--hide-window` | Start with the main window hidden |
| `--autostart-on` | Enable launch on login |
| `--autostart-off` | Disable launch on login |
| `--ctrl-display DISPLAY` | Deprecated compatibility option; has no effect |

Pass options after `scripts/run-native.sh` in the launch command above.

## Development and support

Report problems and request features in the
[GitHub issue tracker](https://github.com/hsantos92/GreenWithEnvi/issues).
Include the commit, GPU, driver, distribution, session type and relevant logs.
See [CONTRIBUTING.md](CONTRIBUTING.md), [CHANGELOG.md](CHANGELOG.md) and
[RELEASING.md](RELEASING.md).

## Credits and license

- Hector Santos (hsantos92): GreenWithEnvi fork and NVML modernization.
- Roberto Leinardi and Gabriele Musco: original GreenWithEnvy application.
- tiheum: Faenza artwork used for the launcher icon.
- NVIDIA: NVML and the `nvidia-ml-py` Python bindings.
- Original contributors, translators, packagers, testers and bug reporters.

GreenWithEnvi continues the original project under
[GPL-3.0-or-later](COPYING.txt). Original copyright notices are retained.
