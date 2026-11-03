#!/usr/bin/env bash
# agnes-cli.sh — Agnes-AI fuer Linux Mint 32-Bit mit nur 2 GB RAM.
# Benoetigt NUR: bash, curl, python3 (vorinstalliert auf Linux Mint).
# KEINE Installation von pip-Paketen noetig -> sehr speicherschonend.
#
# Verwendung:
#   export AGNES_API_KEY="dein_schluessel"          # von https://platform.agnes-ai.com/
#   ./agnes-cli.sh text  "Erzaehle eine Geschichte ueber einen Igel"
#   ./agnes-cli.sh bild  "Ein Igel im Wald, Kinderbuchstil" ausgabe.png
#   ./agnes-cli.sh geschichte "Ein mutiger Igel"     # Text + Bild in ./ausgaben/
#
# API-Doku: https://github.com/AgnesAI-Labs/AgnesAI-Models

set -euo pipefail

BASIS_URL="https://apihub.agnes-ai.com/v1"
TEXT_MODELL="${AGNES_TEXT_MODELL:-agnes-2.5-flash}"
BILD_MODELL="${AGNES_BILD_MODELL:-agnes-image-2.1-flash}"
BILD_GROESSE="${AGNES_BILD_GROESSE:-1024x768}"

if [[ -z "${AGNES_API_KEY:-}" ]]; then
    echo "FEHLER: Bitte zuerst den API-Key setzen:" >&2
    echo '  export AGNES_API_KEY="dein_schluessel"' >&2
    echo "Kostenlosen Schluessel gibt es auf https://platform.agnes-ai.com/" >&2
    exit 1
fi

befehl="${1:-hilfe}"

json_escaped() {
    # Wandelt beliebigen Text in ein gueltiges JSON-String-Wert um (nur Python-Stdlib)
    python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$1"
}

apischlupf() {
    # Pfad $1, JSON-Koerper $2 -> Antwort auf der Standardausgabe
    curl -sS --max-time 180 \
        -H "Authorization: Bearer ${AGNES_API_KEY}" \
        -H "Content-Type: application/json" \
        -d "$2" \
        "${BASIS_URL}$1"
}

text_eros() {
    local prompt="$1"
    local system="Du antwortest AUSSCHLIESSLICH auf Deutsch."
    local koerper
    koerper=$(python3 - "$prompt" "$system" "$TEXT_MODELL" <<'PY'
import json, sys
print(json.dumps({
    "model": sys.argv[3],
    "messages": [
        {"role": "system", "content": sys.argv[2]},
        {"role": "user", "content": sys.argv[1]},
    ],
    "stream": False,
    "max_tokens": 1200,
}))
PY
)
    local antwort
    antwort=$(apischlupf "/chat/completions" "$koerper")
    echo "$antwort" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    if "error" in d:
        raise ValueError(d["error"].get("message", str(d["error"])))
    print(d["choices"][0]["message"]["content"])
except Exception as e:
    sys.stderr.write("Fehler: %s\n" % e)
    sys.exit(1)
'
}

bild_eros() {
    local prompt="$1" datei="${2:-bild.png}"
    local koerper
    koerper=$(python3 - "$prompt" "$BILD_MODELL" "$BILD_GROESSE" <<'PY'
import json, sys
print(json.dumps({
    "model": sys.argv[2],
    "prompt": sys.argv[1],
    "size": sys.argv[3],
    "response_format": "b64_json",
}))
PY
)
    local antwort
    antwort=$(apischlupf "/images/generations" "$koerper")
    echo "$antwort" | python3 -c '
import base64, json, sys
try:
    d = json.load(sys.stdin)
    if "error" in d:
        raise ValueError(d["error"].get("message", str(d["error"])))
    eintrag = d["data"][0]
    daten = b""
    if eintrag.get("b64_json"):
        daten = base64.b64decode(eintrag["b64_json"])
    elif eintrag.get("url"):
        import urllib.request
        daten = urllib.request.urlopen(eintrag["url"], timeout=180).read()
    if not daten:
        raise ValueError("Keine Bilddaten in der Antwort")
    with open(sys.argv[1], "wb") as f:
        f.write(daten)
    print("Bild gespeichert: %s (%d KB)" % (sys.argv[1], len(daten)//1024))
except Exception as e:
    sys.stderr.write("Fehler beim Bild: %s\n" % e)
    sys.exit(1)
' "$datei"
}

case "$befehl" in
    text)
        prompt="${2:?Benutzung: $0 text \"DEIN AUFTRAG\"}"
        text_eros "$prompt"
        ;;
    bild)
        prompt="${2:?Benutzung: $0 bild \"BILDBESCHREIBUNG\" [datei.png]}"
        bild_eros "$prompt" "${3:-bild.png}"
        ;;
    geschichte)
        thema="${2:-Ein mutiger kleiner Igel im Wald}"
        ordner="${3:-ausgaben}"
        mkdir -p "$ordner"
        echo "Erzeuge Geschichte (Modell: $TEXT_MODELL) …"
        text_eros "Erzaehle eine schoene, kinderfreundliche Geschichte auf Deutsch (200-300 Woerter) ueber dieses Thema: ${thema}" > "$ordner/geschichte.txt"
        echo "Geschichte gespeichert: $ordner/geschichte.txt"
        echo "Erzeuge passendes Bild (Modell: $BILD_MODELL) …"
        bild_eros "Kinderbuch-Illustration im warmen Aquarellstil: ${thema}. Freundlich, detailreich, keine Schrift im Bild." "$ordner/illustration.png"
        ;;
    *)
        cat <<EOF
Agnes-AI Kommandozeile (Deutsch, Linux Mint 32-Bit / 2 GB RAM)

Benoetigt: export AGNES_API_KEY="dein_schluessel"  (https://platform.agnes-ai.com/)

Befehle:
  text "AUFTRAG"                 Erzeugt einen deutschen Text (Modell: $TEXT_MODELL)
  bild "BESCHREIBUNG" [DATEI]    Erzeugt ein Bild (Modell: $BILD_MODELL, $BILD_GROESSE)
  geschichte "THEMA" [ORDNER]    Deutsche Geschichte + Illustration im ORDNER (Standard: ausgaben)

Beispiele:
  $0 text "Erzaehle einen Witz ueber Programmierer"
  $0 bild "Ein segelndes Boot bei Sonnenuntergang" urlaubsboot.png
  $0 geschichte "Ein Drache, der Feuer loescht"
EOF
        ;;
esac
