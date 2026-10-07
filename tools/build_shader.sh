#!/bin/sh
# Compile rain.frag into rain.frag.qsb, the only form Qt loads.
#
#   tools/build_shader.sh           rebuild rain.frag.qsb
#   tools/build_shader.sh --check   exit 1 if rain.frag.qsb is out of date
#
# qsb comes from Qt Shader Tools. It is looked up in this order: $QSB,
# /usr/lib/qt6/bin/qsb (Arch: qt6-shadertools), /usr/lib64/qt6/bin/qsb,
# qsb on PATH, then the copy bundled with a PySide6 install (pip install
# PySide6) for whichever python3 is first on PATH.
set -eu

cd "$(dirname "$0")/.."

find_qsb() {
  for candidate in "${QSB:-}" /usr/lib/qt6/bin/qsb /usr/lib64/qt6/bin/qsb "$(command -v qsb 2>/dev/null || true)"; do
    if [ -n "$candidate" ] && [ -x "$candidate" ]; then
      echo "$candidate"
      return 0
    fi
  done
  bundled=$(python3 -c 'import os, PySide6; print(os.path.join(os.path.dirname(PySide6.__file__), "qsb"))' 2>/dev/null || true)
  if [ -n "$bundled" ] && [ -x "$bundled" ]; then
    echo "$bundled"
    return 0
  fi
  return 1
}

if ! QSB_BIN=$(find_qsb); then
  echo "build_shader: qsb not found. Install qt6-shadertools (Arch) or 'pip install PySide6', or set QSB=/path/to/qsb." >&2
  exit 2
fi

export LANG=C.UTF-8
if [ "${1:-}" = "--check" ]; then
  tmp=$(mktemp)
  trap 'rm -f "$tmp"' EXIT
  "$QSB_BIN" --glsl 440 -o "$tmp" rain.frag
  if cmp -s "$tmp" rain.frag.qsb; then
    echo "rain.frag.qsb is up to date."
  else
    echo "rain.frag.qsb is stale: run tools/build_shader.sh" >&2
    exit 1
  fi
else
  "$QSB_BIN" --glsl 440 -o rain.frag.qsb rain.frag
  echo "Built rain.frag.qsb with $QSB_BIN"
fi
