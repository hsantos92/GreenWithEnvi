# Contributing to GreenWithEnvi

Use the [GitHub repository](https://github.com/hsantos92/GreenWithEnvi) for
issues and pull requests. The NVML implementation is on `nvml-driver-compat`.

## Reporting problems

Include the commit or version, Linux distribution, desktop, Wayland or X11
session, GPU model, NVIDIA driver version, steps to reproduce, expected behavior
and terminal output from running with `--debug`. For control failures, include
the authentication result and driver error. Remove private information from logs.

## Development

Follow [NVML-MIGRATION.md](NVML-MIGRATION.md) to set up the native environment
and run unit tests, backend type checks and Pylint error checks. Build resources
with `ninja -C build/native` after the initial Meson setup. Follow the existing
Python style and add regression coverage for behavior changes.

GPU control tests use mocked NVML. Report real hardware validation separately,
including GPU, driver and operations exercised. Do not describe mocked writes
as verified physical fan, clock or power changes.

Keep documentation and [CHANGELOG.md](CHANGELOG.md) current. Preserve existing
profile compatibility and original copyright and contributor attribution.
