#!/data/data/com.termux/files/usr/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC_DIR="$SCRIPT_DIR/termux_shortcuts"
DST_DIR="$HOME/.shortcuts"

mkdir -p "$DST_DIR"
cp "$SRC_DIR"/* "$DST_DIR"/
chmod +x "$DST_DIR"/tecnomat-*

echo "Shortcut installati in $DST_DIR"
echo "Apri Termux:Widget e usa:"
echo "- tecnomat-update"
echo "- tecnomat-reinstall"
echo "- tecnomat-healthcheck"
