#!/data/data/com.termux/files/usr/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_BIN="$PREFIX/bin/tecnomat"

chmod +x "$SCRIPT_DIR/tecnomat_termux.py"
ln -sf "$SCRIPT_DIR/tecnomat_termux.py" "$TARGET_BIN"

echo "Comando installato: tecnomat"
echo "Ora puoi usarlo cosi: tecnomat \"silicone bagno\""
