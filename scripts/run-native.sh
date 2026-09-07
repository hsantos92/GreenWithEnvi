#!/usr/bin/env bash
# Run this checkout without installing GWE system-wide.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
gwe_python="${GWE_PYTHON:-python3}"
gwe_python="$(command -v "$gwe_python")"
export PATH="$(dirname -- "$gwe_python"):$PATH"
if [[ ! -f build/native/build.ninja ]]; then
    meson setup build/native --prefix="$PWD/build/native-install"
fi
ninja -C build/native
export MESON_BUILD_ROOT="$PWD/build/native"
export MESON_SOURCE_ROOT="$PWD"
exec "$gwe_python" build/native/bin/gwe "$@"
