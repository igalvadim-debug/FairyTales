# Agnes-KI Werkzeuge für Linux Mint (32-Bit, 2 GB RAM)

Diese Werkzeuge erzeugen **deutsche Texte/Geschichten** und **Bilder** über die
offizielle **Agnes-AI-API** (<https://github.com/AgnesAI-Labs/AgnesAI-Models>,
Basis-URL `https://apihub.agnes-ai.com/v1`).

Sie sind bewusst **minimal gehalten**: nur Bash, `curl` und die
Python-Standardbibliothek — **keine pip-Pakete**, kein Electron, keine schweren
Frameworks. Dadurch laufen sie problemlos auf einem alten **Linux-Mint-32-Bit-
Rechner mit nur 2 GB RAM** (Belegung: ca. 20–50 MB).

## API-Key einrichten (einmalig)

1. Kostenlosen Schlüssel erstellen auf: <https://platform.agnes-ai.com/>
2. In der Shell setzen:
   ```bash
   export AGNES_API_KEY="dein_schluessel"
   ```
   Dauerhaft (in `~/.bashrc` eintragen):
   ```bash
   echo 'export AGNES_API_KEY="dein_schluessel"' >> ~/.bashrc && source ~/.bashrc
   ```

## Installation

```bash
cd tool
./install.sh
```

Der Installer kopiert die Befehle nach `~/.local/bin` und fragt (optional)
nach dem API-Schlüssel, den er sicher in `~/.agnes_api_key` (nur für dich
lesbar) ablegt.

## Verwendete Agnes-Modelle

| Zweck | Modell | Endpunkt |
| --- | --- | --- |
| Texte / Geschichten | `agnes-2.5-flash` (auch `agnes-2.0-flash`, `agnes-1.5-flash`) | `POST /v1/chat/completions` |
| Bilder | `agnes-image-2.1-flash` (auch `agnes-image-2.0-flash`) | `POST /v1/images/generations` |

Alle Antworten werden per Systemanweisung ausdrücklich **auf Deutsch** erzeugt.

## Befehlszeile (speicherschonend, empfohlen für 2 GB RAM)

```bash
agnes-cli text "Erzähle einen kurzen Witz über Programmierer"
agnes-cli bild "Ein roter Fuchs im Schnee, Aquarellstil" fuchs.png
agnes-cli geschichte "Ein mutiger kleiner Igel"        # Text + Bild → ./ausgaben/
```

Feinsteuerung über Umgebungsvariablen:
`AGNES_TEXT_MODELL`, `AGNES_BILD_MODELL`, `AGNES_BILD_GROESSE`
(z. B. `export AGNES_BILD_GROESSE=1024x1024`).

## Python-Client (mehr Optionen)

```bash
python3 tool/agnes_client.py text --prompt "Ein Gedicht über den Herbst" -o gedicht.txt
python3 tool/agnes_client.py bild --prompt "Ein Drache über einem Bergdorf" -o drache.png --size 1536x1024
python3 tool/agnes_client.py geschichte "Ein Schiff aus Papier" --ausgabe-dir geschichten
```

Ohne API-Key erzeugt `geschichte` eine lokale Notgeschichte, damit das
Programm nie einfach abstürzt.

## Grafische Oberfläche (Tkinter, ~40 MB RAM)

```bash
sudo apt-get install -y python3-tk   # falls nicht vorhanden
python3 tool/agnes_gui.py
```

Thema eingeben → **„Geschichte erzeugen“** oder **„Bild erzeugen“** →
mit **„Speichern“** als Datei sichern. Netzwerkaufrufe laufen in einem
Hintergrundthread, das Fenster bleibt bedienbar. Eine kleine
Bild-Vorschau erscheint nur, wenn zusätzlich `python3-pil` installiert ist —
sie ist optional.

## Alles auf der Festplatte (kein ESP, keine SD-Karte nötig)

Es gibt **kein ESP32-P4-Panel mehr** — alles läuft nur noch auf dem
Linux-Rechner, und diese Werkzeuge brauchen auch **keine SD-/microSD-Karte**.
Alle erzeugten Texte und Bilder werden direkt auf die **Festplatte**
geschrieben:

- Standard-Ausgabeordner: `./ausgaben/` im aktuellen Verzeichnis.
- frei wählbar: `agnes-cli geschichte "Thema" ~/Geschichten` bzw.
  `python3 agnes_client.py geschichte "Thema" --ausgabe-dir ~/Geschichten`.
- Das eigentliche Märchenbuch ist das Linux-Programm `maerchenbuch.py`
  im Hauptordner dieses Projekts (Geschichten/Bilder/Vorlesen direkt auf
  dem Rechner) — es wird nichts geflasht und nichts auf eine Karte kopiert.

## Tipps für 32-Bit / 2 GB RAM

- Bilder in **1024×768** oder **1024×1024** erzeugen (1-Klasse-Auflösung =
  höchste Rate-Limits, kleinster Speicherbedarf beim Download).
- Die Skripte laden Bilddaten komplett im Arbeitsspeicher hoch; bei den
  üblichen PNG-Größen (< 3 MB) ist das unkritisch.
- Kein Browser/Electron nötig — alles läuft über `curl`/`urllib`.

## Fehlerbehandlung

| Meldung | Bedeutung / Lösung |
| --- | --- |
| `AGNES_API_KEY ist nicht gesetzt` | Schlüssel wie oben einrichten |
| HTTP 401 `Invalid token` | Schlüssel falsch/abgelaufen → neuen anlegen |
| HTTP 429 | Rate-Limit erreicht (Free: 30 Anfragen/min) → kurz warten |
| Netzwerkfehler | Internetverbindung prüfen |

Fehlercodes im Detail: <https://github.com/AgnesAI-Labs/AgnesAI-Models/blob/main/docs/ERROR_CODES.md>
