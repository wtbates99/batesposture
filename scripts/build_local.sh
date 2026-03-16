#!/usr/bin/env bash
# Build a standalone BatesPosture app on macOS or Linux.
# Usage: ./scripts/build_local.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> Installing / syncing dev dependencies…"
uv sync --all-groups

# ── macOS: convert icon to .icns ───────────────────────────────────────────
if [[ "$(uname)" == "Darwin" ]]; then
  echo "==> Converting icon.png → icon.icns (macOS)…"
  ICONSET="src/static/icon.iconset"
  mkdir -p "$ICONSET"
  for size in 16 32 64 128 256 512; do
    sips -z $size $size src/static/icon.png \
      --out "$ICONSET/icon_${size}x${size}.png"        > /dev/null 2>&1
    sips -z $((size*2)) $((size*2)) src/static/icon.png \
      --out "$ICONSET/icon_${size}x${size}@2x.png"     > /dev/null 2>&1
  done
  iconutil -c icns "$ICONSET" -o src/static/icon.icns
  echo "    → src/static/icon.icns created"
fi

echo "==> Running PyInstaller…"
uv run pyinstaller batesposture.spec --noconfirm

echo ""
if [[ "$(uname)" == "Darwin" ]]; then
  echo "✅  Build complete: dist/BatesPosture.app"
  echo ""
  echo "   To create a DMG:"
  echo "   hdiutil create -volname 'BatesPosture' \\"
  echo "     -srcfolder dist/BatesPosture.app \\"
  echo "     -ov -format UDZO BatesPosture.dmg"
else
  echo "✅  Build complete: dist/BatesPosture/"
  echo ""
  echo "   To create a tarball:"
  echo "   tar -czf BatesPosture-Linux.tar.gz -C dist BatesPosture"
fi
