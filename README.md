# CrowPanel P4 Märchen-Storybook — ESP32-P4 Firmware (Festplatten-Version)

Interaktives Märchenbuch für **Elecrow CrowPanel Advanced ESP32-P4** mit
1024 × 600 Touchdisplay. Diese Version kommt **ohne microSD-Karte** aus:
Alle Inhalte (Bilder, Animationen, Erzähl-Audio) sind bereits in der
Firmware enthalten und werden **direkt von der Festplatte** des Flash-PCs
auf den Panel geflasht. Es wird nichts auf eine SD-/TF-Karte kopiert.

## Was wird benötigt

- **CrowPanelv1.2_StoryBookP4_SPIFFS_v1.1.zip** — die komplette Firmware
  (enthält alle Assets im SPIFFS-Image; alles bleibt auf der Festplatte).
- Windows-PC oder Linux-PC zum Flashen.
- Zwei Lautsprecher an **SPK-L** und **SPK-R**.
- Ein Daten-USB-C-Kabel.

## Flashen (Windows)

1. CH341-Treiber installieren:
   [CH341SER herunterladen](https://www.wch-ic.com/downloads/CH341SER_ZIP.html)
2. `CrowPanelv1.2_StoryBookP4_SPIFFS_v1.1.zip` auf der **Festplatte**
   vollständig entpacken (kein SD-Karten-Schritt nötig).
3. Panel über den **UART0 USB-C**-Port anschließen.
4. `CrowPanel_P4_SPIFFS_flasher/CrowPanel_P4_SPIFFS_flasher.exe` starten.
5. COM-Port wählen (sonst **Refresh**), **„Clean install (erase entire flash)"**
   aktivieren, dann **Flash panel**.
6. Warten bis „Firmware installed successfully". Panel startet neu.

## Flashen (Linux, z. B. Linux Mint)

```bash
sudo apt-get install -y python3-serial esptool
unzip CrowPanelv1.2_StoryBookP4_SPIFFS_v1.1.zip -d storybook
cd storybook/CrowPanel_P4_SPIFFS_flasher/firmware
esptool --chip esp32p4 --port /dev/ttyUSB0 --baud 921600 write_flash \
  0x0 bootloader.bin \
  0x8000 partition-table.bin \
  0x10000 crowpanel_p4_fairytale.bin \
  0x200000 spiffs.bin   # Adresse je nach Partitionstabelle anpassen
```

Hinweis: Die exakten Flash-Adressen zeigt der Windows-Flasher aus dem ZIP;
im Zweifel die dort angezeigte Adresse für `spiffs.bin` verwenden.
(Asset-Quelldateien: Zweig `source-code`.)

## USB-C-Ports und Stromversorgung

- **UART0** — Flashen und serielle Kommunikation (Hauptanschluss).
- **USB 2.0** — nativer USB-Port, kann zusätzlich 5 V liefern.

Falls der Panel unter Last instabil wird (Display schwarz, Resets,
Audioabbrüche): zweites USB-C-Kabel an **USB 2.0** für Zusatzstrom anschließen.

## Fehlerbehebung

- Panel nicht erkannt → über UART0 neu verbinden, COM-Port-Besitzer schließen, **Refresh**.
- Anwendung startet nicht → beide Lautsprecher an SPK-L/SPK-R prüfen; beim
  ersten Start ggf. Panel neu starten. Eine SD-Karte ist **nicht** erforderlich.

## Deutsche KI-Werkzeuge (Agnes-AI, Linux Mint 32-Bit / 2 GB RAM)

In `tool/` befinden sich deutsche Kommandozeilen- und GUI-Programme, die über
die **Agnes-AI-API** (<https://github.com/AgnesAI-Labs/AgnesAI-Models>) Texte
und Bilder erzeugen — für Märchen mit eigenen Themen. Alle Ausgaben werden
**direkt auf die Festplatte** gespeichert (Standardordner `./ausgaben/`,
frei wählbar mit `--ausgabe-dir` bzw. als Argument). Sie laufen auf alter
Hardware (32-Bit, 2 GB RAM), weil sie nur Bash/curl/Python-Standardbibliothek
nutzen.

Anleitung: [tool/README_DE.md](tool/README_DE.md)
