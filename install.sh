#!/bin/sh
# Installe la commande `brev` pour l'utilisateur courant (Linux, macOS, WSL).
set -e
command -v python3 >/dev/null || { echo "Python 3 est requis."; exit 1; }
command -v gcc >/dev/null || command -v cc >/dev/null || { echo "Un compilateur C (gcc ou clang) est requis."; exit 1; }
SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.local/share/brev"
BIN="$HOME/.local/bin"
mkdir -p "$DEST" "$BIN"
cp -R "$SRC"/*.py "$SRC"/SPEC.md "$SRC"/GUIDE.md "$SRC"/tests "$SRC"/ex "$DEST"/ 2>/dev/null || true
chmod +x "$DEST/brev.py"
ln -sf "$DEST/brev.py" "$BIN/brev"
echo "brev installé dans $BIN/brev"
case ":$PATH:" in
  *":$BIN:"*) ;;
  *) echo "Ajoute cette ligne à ton ~/.bashrc ou ~/.zshrc :  export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
esac
"$BIN/brev" version
