#!/usr/bin/env bash
# install.sh — installiert das Maerchenbuch auf einem reinen Linux-Rechner.
# WICHTIG: Es wird KEIN ESP32/P4-Panel mehr bentigt und KEINE SD-Karte!
# Alles laeuft direkt auf dem Rechner (Linux Mint, Debian, Ubuntu, ...).
# Alle Inhalte gehen auf die FESTPLATTE; es werden keine pip-Pakete
# installiert (spart RAM und vermeidet 32-Bit-Probleme).
set -euo pipefail

echo "== Maerchenbuch Installation (Linux, ohne ESP) =="

HERE="$(cd "$(dirname "$0")" && pwd)"

# 1. Voraussetzungen pruefen / installieren
for programm in bash curl python3; do
    if ! command -v "$programm" >/dev/null 2>&1; then
        echo "Programm fehlt: $programm — versuche zu installieren…"
        sudo apt-get update && sudo apt-get install -y --no-install-recommends "$programm"
    fi
done
echo "python3 Version: $(python3 --version)"

# 2. Tkinter fuer die grafische Oberflaeche (entspricht dem frueheren Display)
if ! python3 -c "import tkinter" >/dev/null 2>&1; then
    echo "Tkinter fehlt — installiere python3-tk…"
    sudo apt-get install -y --no-install-recommends python3-tk
fi

# 3. Sprachausgabe (der Erzahler): espeak-ng mit deutscher Stimme
if ! command -v espeak-ng >/dev/null 2>&1 && ! command -v espeak >/dev/null 2>&1 \
   && ! command -v spd-say >/dev/null 2>&1; then
    echo "Installiere espeak-ng (deutsche Stimme zum Vorlesen)…"
    sudo apt-get install -y --no-install-recommends espeak-ng espeak-ng-data || \
        sudo apt-get install -y --no-install-recommends espeak
fi

# 4. Programm nach ~/.local/bin installieren
ZIEL="$HOME/.local/bin"
mkdir -p "$ZIEL"
install -m 755 "$HERE/maerchenbuch.py" "$ZIEL/maerchenbuch"
echo "Installiert: $ZIEL/maerchenbuch"

# Agnes-KI-Werkzeuge aus tool/ ebenfalls anbieten (optional, gleiche API)
if [[ -d "$HERE/tool" ]]; then
    install -m 755 "$HERE/tool/agnes_client.py" "$ZIEL/agnes-client"
    install -m 755 "$HERE/tool/agnes-cli.sh"    "$ZIEL/agnes-cli"
    echo "Zusaetzlich: agnes-client und agnes-cli (Text/Bild-Komfortfunktionen)"
fi

# 5. PATH eintragen, falls noetig
if ! echo "$PATH" | tr ':' '\n' | grep -qx "$ZIEL"; then
    for datei in "$HOME/.bashrc" "$HOME/.profile"; do
        grep -q 'HOME/.local/bin' "$datei" 2>/dev/null || \
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$datei"
    done
    echo "Bitte einmal abmelden/anmelden ODER ausfuehren:  source ~/.bashrc"
fi

# 6. API-Key dauerhaft merken (optional, interaktiv)
if [[ -z "${AGNES_API_KEY:-}" && ! -f "$HOME/.agnes_api_key" ]]; then
    echo
    echo "API-Key einrichten (https://platform.agnes-ai.com/ -> API Keys)."
    echo "Ohne Schluessel laufen lokale Notgeschichten — der Schluessel ist optional."
    echo "Der Schluessel wird lokal in $HOME/.agnes_api_key gespeichert (nur lesbar fuer dich)."
    read -r -s -p "API-Key eingeben (oder Enter zum Ueberspringen): " schluessel
    echo
    if [[ -n "${schluessel:-}" ]]; then
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

# 7. Datenordner auf der Festplatte anlegen
DATEN="${MAERCHEN_ORDNER:-$HOME/Maerchen}"
mkdir -p "$DATEN"
grep -q 'MAERCHEN_ORDNER' "$HOME/.bashrc" 2>/dev/null || \
    echo "export MAERCHEN_ORDNER=\"$DATEN\"" >> "$HOME/.bashrc"
echo "Maerchen-Ordner auf der Festplatte: $DATEN"

echo
echo "== Fertig! Teste es so: =="
echo '  maerchenbuch                                   # Fenster oeffnen'
echo '  maerchenbuch --neu "Ein tapferer Igel" --bild  # Geschichte + Bild per KI'
echo '  maerchenbuch --liste                           # gespeicherte Maerchen'
echo '  maerchenbuch --sprache                         # veruegbare Stimmen zeigen'
