#!/data/data/com.termux/files/usr/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_BIN="$PREFIX/bin/tecnomat"
PERSIST_DIR="$HOME/.config/tecnomat"
PERSIST_ENV="$PERSIST_DIR/.env"
LOCAL_ENV="$SCRIPT_DIR/.env"

chmod +x "$SCRIPT_DIR/tecnomat_termux.py"
ln -sf "$SCRIPT_DIR/tecnomat_termux.py" "$TARGET_BIN"

# Persist .env outside repo so git operations never wipe credentials.
mkdir -p "$PERSIST_DIR"
if [ -f "$LOCAL_ENV" ]; then
  cp "$LOCAL_ENV" "$PERSIST_ENV"
elif [ -f "$PERSIST_ENV" ]; then
  cp "$PERSIST_ENV" "$LOCAL_ENV"
fi

echo "Comando installato: tecnomat"
echo "Ora puoi usarlo cosi: tecnomat \"silicone bagno\""
echo "Config persistente: $PERSIST_ENV"
