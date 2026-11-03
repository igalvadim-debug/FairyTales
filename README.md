# Märchen-Storybook — jetzt als Linux-Programm (ohne ESP!)

Du hast recht: **Es gibt keinen ESP mehr.** Die frühere Idee war eine Firmware
für ein *Elecrow CrowPanel Advanced ESP32-P4* mit 1024 × 600-Touchdisplay.
Dieses Projekt wurde vollständig auf einen **reinen Linux-Rechner** umgestellt:

| Früher (ESP32-P4) | Heute (nur Linux-Rechner) |
| --- | --- |
| Firmware `.bin` + SPIFFS-Image, geflasht per esptool | Python-Programm `maerchenbuch.py`, gestartet per Konsole/Doppelklick |
| 1024×600-Touchdisplay des Panels | normales Fenster (Tkinter) auf deinem Monitor |
| Touch-Wischen = Blättern | Klick / Pfeiltasten / Leertaste / Touchscreen |
| Erzähl-Audio aus der Firmware | Vorlesen über Agnes-AI-Sprachausgabe, `espeak-ng`, `spd-say` oder `festival` |
| Assets im SPIFFS-Image / auf SD-Karte | alles auf der **Festplatte** (Ordner `~/Maerchen` bzw. `./maerchen`) |
| Flash-PC, CH341-Treiber, USB-C-Kabel | kein Flashen, keine Treiber, keine SD-/TF-Karte |

Das frühere Firmware-ZIP und der `sd_card/`-Ordner wurden aus diesem Zweig
entfernt — es wird nichts mehr auf ein Panel geflasht.

## Was wird benötigt

- Ein beliebiger Linux-Rechner (z. B. Linux Mint, auch 32-Bit mit 2 GB RAM)
- `python3` + Tkinter (`sudo apt-get install python3-tk`)
- Zum Vorlesen: `sudo apt-get install espeak-ng` (deutsche Stimme)
- Optional: API-Key der **Agnes-AI-API** (<https://platform.agnes-ai.com/>),
  damit echte KI-Geschichten und Bilder erzeugt werden — ohne Key laufen
  lokale Notgeschichten, das Programm stürzt nie ab.

## Installation

```bash
cd <Projektordner>
./install.sh
source ~/.bashrc
```

Der Installer prüft Tkinter/espeak-ng, legt den Festplatten-Ordner an und
installiert den Befehl `maerchenbuch` nach `~/.local/bin`.

## Start

```bash
maerchenbuch                      # grafisches Fenster öffnen
maerchenbuch --thema "Ein Igel"   # Fenster, Thema schon eingetragen
```

Im Fenster: Thema eintippen → **„Neues Maerchen“** → die Geschichte erscheint
seitenweise; mit **„Vorlesen“** erzählt der Rechner sie laut, mit
**„Maerchen oeffnen“** holst du gespeicherte Geschichten zurück.

## Kommandozeile (für Skripte und sehr schwache Rechner)

```bash
python3 maerchenbuch.py --neu "Ein tapferer Drache" --bild --vorlesen
python3 maerchenbuch.py --liste
python3 maerchenbuch.py --oeffnen 1 --vorlesen
python3 maerchenbuch.py --sprache    # zeigt verfügbare Stimmen
python3 maerchenbuch.py --hilfe
```

## Alles auf der Festplatte

Jedes Märchen wird als eigener Ordner gespeichert:

```
~/Maerchen/
└── der-tapfere-drache_20261103-1015/
    ├── geschichte.md        # Text
    ├── illustration.png     # KI-Bild (falls API-Key gesetzt)
    └── meta.json            # Titel, Datum, Dateien
```

Standardordner ist `./maerchen` neben dem Skript; frei wählbar mit
`--datenordner PFAD` oder Umgebungsvariable `MAERCHEN_ORDNER`
(der Installer setzt sie automatisch auf `~/Maerchen`).

## Die alten Panel-Animationen

In `geschichten/` liegen noch die früheren Animationsdateien des Panels
(`book_open.cfa`, `bird_talk.gif` …). Sie sind nur noch Archiv — das Linux-
Programm braucht sie nicht; Blättern und der sprechende Vogel werden durch
die Seitenansicht und die Sprachausgabe ersetzt.

## Deutsche KI-Werkzeuge (Agnes-AI)

In `tool/` bleiben die zusätzlichen Kommandozeilen-/GUI-Programme, die über
dieselbe Agnes-AI-API Texte und Bilder erzeugen (Ausgaben ebenfalls direkt
auf die Festplatte): [tool/README_DE.md](tool/README_DE.md)

## Fehlerbehebung

- Kein Ton beim Vorlesen → `sudo apt-get install espeak-ng`, dann
  `python3 maerchenbuch.py --sprache` prüfen.
- „Tkinter fehlt“ → `sudo apt-get install python3-tk`.
- Nur Notgeschichten → API-Key setzen: `export AGNES_API_KEY="..."`
  (oder Datei `~/.agnes_api_key`).
- HTTP 401 → Schlüssel falsch/abgelaufen; HTTP 429 → Rate-Limit, kurz warten.
