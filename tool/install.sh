#!/usr/bin/env bash
# install.sh — installiert den Agnes-AI-Client auf Linux Mint (auch 32-Bit, 2 GB RAM).
# Es werden KEINE Python-Pakete installiert (spart RAM und avoids 32-Bit-Probleme);
# es wird nur die ohnehin vorhandene Standardbibliothek von python3 benutzt.
set -euo pipefail

echo "== Agnes-AI-Client Installation (Deutsch) =="

# 1. Voraussetzungen pruefen (auf Linux Mint standardmaessig vorhanden)
for programm in bash curl python3; do
    if ! command -v "$programm" >/dev/null 2>&1; then
        echo "Programm fehlt: $programm — versuche zu installieren…"
        sudo apt-get update && sudo apt-get install -y --no-install-recommends "$programm"
    fi
done
echo "python3 Version: $(python3 --version)"

# 2. Skripte nach ~/.local/bin kopieren
ZIEL="$HOME/.local/bin"
mkdir -p "$ZIEL"
HERE="$(cd "$(dirname "$0")" && pwd)"
install -m 755 "$HERE/agnes_client.py" "$ZIEL/agnes-client"
install -m 755 "$HERE/agnes-cli.sh"    "$ZIEL/agnes-cli"
echo "Installiert nach: $ZIEL/agnes-client und $ZIEL/agnes-cli"

# 3. PATH eintragen, falls noetig
if ! echo "$PATH" | tr ':' '\n' | grep -qx "$ZIEL"; then
    for datei in "$HOME/.bashrc" "$HOME/.profile"; do
        grep -q 'HOME/.local/bin' "$datei" 2>/dev/null || \
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$datei"
    done
    echo "Bitte einmal abmelden/anmelden ODER ausfuehren:  source ~/.bashrc"
fi

# 4. API-Key dauerhaft merken (optional, interaktiv)
if [[ -z "${AGNES_API_KEY:-}" ]]; then
    echo
    echo "API-Key einrichten (https://platform.agnes-ai.com/ -> API Keys)."
    echo "Der Schluessel wird lokal in $HOME/.agnes_api_key gespeichert (nur lesbar fuer dich)."
    read -r -s -p "API-Key eingeben (oder Enter zum Ueberspringen): " schluessel
    echo
    if [[ -n "$schluessel" ]]; then
        umask 077
        printf '%s\n' "$schluessel" > "$HOME/.agnes_api_key"
        if ! grep -q '.agnes_api_key' "$HOME/.bashrc" 2>/dev/null; then
            echo 'export AGNES_API_KEY="$(cat "$HOME/.agnes_api_key" 2>/dev/null)"' >> "$HOME/.bashrc"
        fi
        echo "Schluessel gespeichert. Bitte:  source ~/.bashrc"
    else
        echo "Uebersprungen. Spaeter setzen mit:"
        echo '  export AGNES_API_KEY="dein_schluessel"'
    fi
fi

echo
echo "== Fertig! Teste es so: =="
echo '  agnes-cli text "Erzaehle einen kurzen Witz auf Deutsch"'
echo '  agnes-cli bild "Ein roter Fuchs im Schnee, Aquarellstil" fuchs.png'
echo '  agnes-client geschichte "Ein mutiger kleiner Igel"'
