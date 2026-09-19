# GreenWithEnvi native NVML backend

This branch replaces the X11 NV-CONTROL backend with NVML. It supports Wayland
and X11 without Coolbits or `--ctrl-display`. The latter option is accepted as
a deprecated no-op. GPU discovery, telemetry, clocks, fan duty and individual
fan RPMs come from NVML. Memory uses the v2 query: used memory matches
`nvidia-smi` accounting on the tested driver, while reserved memory is shown
separately in a tooltip. If v2 is unavailable, memory fields remain unavailable
rather than silently switching to different accounting. Optional unsupported sensors stay blank; driver loss
is treated as a refresh failure.

## Run from this checkout

Use Python 3.10 or newer. Install the distribution's GTK 3, libdazzle,
libnotify, PyGObject, Cairo, Meson, Ninja and NVIDIA driver/NVML packages.
On Arch the corresponding packages include `gtk3`, `libdazzle`, `libnotify`,
`python-gobject`, `python-cairo`, `meson`, `ninja`, and `nvidia-utils`.
A desktop polkit authentication agent and `pkexec` are needed for controls.

```sh
python3 -m venv --system-site-packages ~/.cache/gwe-dev
~/.cache/gwe-dev/bin/pip install -r requirements.txt
GWE_PYTHON=~/.cache/gwe-dev/bin/python bash scripts/run-native.sh
```

The launcher builds resources in `build/native` and runs this checkout. It
does not install GWE system-wide. Existing GWE profiles/settings are used.
The Python dependency ranges allow current system GTK and matplotlib packages;
`nvidia-ml-py` is pinned because we use its native structure definitions.

## Controls and authorization

Applying a setting starts a small worker through `pkexec`; the GTK application
continues to run as the desktop user. Each worker is bound to one GPU UUID.
It accepts only fan, automatic fan, clock-offset and power-limit commands.
Values are validated against driver limits. By default authentication authorizes
this checkout's worker and Python environment; use a trusted checkout and
environment. The optional [system helper](CONTROL-HELPER.md) installs root-owned
copies and a narrow polkit rule for passwordless control from one active local
user. When present, the app uses that helper instead of development Python.

Fan curves refresh the worker within the UI's 1–10 second refresh interval.
The worker attempts to restore firmware fan control on disconnect, error, or
15 seconds without a command, then exits. Restoration errors are reported on
stderr. An idle session may require authentication again for a later action.
Only fans touched by that worker are restored on exit. Explicit Auto restores
all fans on the selected GPU. Power limits and clock offsets persist according
to driver behavior; they are not automatically reset on exit.

Memory profiles retain GWE's previous MHz units: a profile's memory offset is
multiplied by two for the NVML transfer-rate offset, matching NVIDIA's
nvidia-settings implementation. Clock controls target P0. If the second clock
write fails, the first is rolled back; rollback errors propagate as failures.
Fan curve values are clamped to the driver's supported fan-speed range.

Fan hysteresis tracks the temperature of the last changed duty command. With a
2 °C band, readings of 70 → 69 → 68 °C release the held duty at 68 °C even
though each individual change is only 1 °C. Duty increases are immediate.
Repeated worker keepalive commands do not move the temperature reference.
Clicking Apply resets hysteresis and evaluates the selected curve immediately;
edits to the applied curve or hysteresis setting also reset the reference.

Interpolation sorts saved points by temperature. The graph and controller use
the same endpoints, preserving saved limits such as a quiet curve ending at
50% instead of drawing an artificial 100% endpoint. Profile records themselves
are not rewritten.


Flatpak controls are disabled: the native worker cannot safely be launched from
the old sandbox packaging. This checkout's legacy Flatpak submodule/manifest
has not been migrated or validated. Use the native launcher for this version.

## Validation

```sh
~/.cache/gwe-dev/bin/python -m unittest discover -s tests -v
~/.cache/gwe-dev/bin/mypy --explicit-package-bases --follow-imports=skip \
  gwe/repository/nvidia_repository.py gwe/repository/nvml_control.py \
  gwe/repository/nvml_worker.py
PYTHONPATH="$PWD" ~/.cache/gwe-dev/bin/pylint --rcfile=/dev/null -E \
  gwe/repository/nvidia_repository.py gwe/repository/nvml_control.py \
  gwe/repository/nvml_worker.py gwe/presenter/main_presenter.py
```

The old pylintrc contains options removed by current Pylint; the command above
runs error checks without that configuration. Existing PyGObject analysis
limitations remain outside these backend checks.

Tested with an RTX 4090, NVIDIA 610.57.04, Wayland, Python 3.14, PyGObject
3.56.3 and matplotlib 3.11.1. Live monitoring and the GTK window were verified.
Control writes, range validation, rollback and watchdog restoration are tested
with mocked NVML. The user reported the application working on this system;
physical fan tracking under load and GPU clock/power writes have not been
independently verified.

References:
- NVIDIA 570 transition: https://www.nvidia.com/en-gb/drivers/details/240605/
- NVML commands: https://docs.nvidia.com/deploy/nvml-api/group__nvmlDeviceCommands.html
- NVIDIA settings implementation: https://github.com/NVIDIA/nvidia-settings/blob/main/src/libXNVCtrlAttributes/NvCtrlAttributesNvml.c
