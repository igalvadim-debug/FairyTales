#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agnes-AI-Client — sehr leichter HTTP-Client fuer Linux Mint (32-Bit, 2 GB RAM).

Benutzt nur die Standardbibliothek (urllib), keine schweren Pakete wie
requests oder openai. Damit laeuft er auch auf einem alten 32-Bit-System.

Unterstuetzte Endpunkte (OpenAI-kompatibel, Basis-URL:
https://apihub.agnes-ai.com/v1):

  * Texte   : POST /chat/completions   (Modelle: agnes-2.5-flash, agnes-2.0-flash, agnes-1.5-flash)
  * Bilder  : POST /images/generations (Modelle: agnes-image-2.1-flash, agnes-image-2.0-flash)

Dokumentation: https://github.com/AgnesAI-Labs/AgnesAI-Models
API-Key:       https://platform.agnes-ai.com/  -> Umgebungsvariable AGNES_API_KEY
"""

import argparse
import base64
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.request

BASIS_URL = "https://apihub.agnes-ai.com/v1"

TEXT_MODELLE = ["agnes-2.5-flash", "agnes-2.0-flash", "agnes-1.5-flash"]
BILD_MODELLE = ["agnes-image-2.1-flash", "agnes-image-2.0-flash"]

# Erlaubte Bildgroessen (flexible Groessen laut Modell-Katalog)
BILD_GROESSEN = [
    "1024x768", "768x1024", "1024x1024",
    "1280x720", "720x1280", "1536x1024", "1024x1536",
]


def api_key():
    schluessel = os.environ.get("AGNES_API_KEY", "").strip()
    if not schluessel:
        raise SystemExit(
            "FEHLER: Umgebungsvariable AGNES_API_KEY ist nicht gesetzt.\n"
            "Erstelle einen Schluessel auf https://platform.agnes-ai.com/ und setze ihn:\n"
            '  export AGNES_API_KEY="dein_schluessel"'
        )
    return schluessel


def post_json(pfad, daten):
    """Fuehrt einen POST-Request mit JSON aus und gibt die Antwort als dict zurueck."""
    anfrage = urllib.request.Request(
        BASIS_URL + pfad,
        data=json.dumps(daten).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + api_key(),
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=180) as antwort:
            return json.loads(antwort.read().decode("utf-8"))
    except urllib.error.HTTPError as fehler:
        text = fehler.read().decode("utf-8", errors="replace")
        raise SystemExit(
            "FEHLER von der Agnes-API (HTTP %s):\n%s" % (fehler.code, text)
        )
    except urllib.error.URLError as fehler:
        raise SystemExit("Netzwerkfehler: %s\nPruefe deine Internetverbindung." % fehler.reason)


def text_generieren(prompt, system, modell, max_tokens):
    nachrichten = []
    if system:
        nachrichten.append({"role": "system", "content": system})
    nachrichten.append({"role": "user", "content": prompt})

    antwort = post_json("/chat/completions", {
        "model": modell,
        "messages": nachrichten,
        "stream": False,
        "max_tokens": max_tokens,
    })
    return antwort["choices"][0]["message"]["content"]


def bild_generieren(prompt, datei, modell, groesse):
    antwort = post_json("/images/generations", {
        "model": modell,
        "prompt": prompt,
        "size": groesse,
        "response_format": "b64_json",
    })
    eintrag = antwort["data"][0]
    if "b64_json" in eintrag and eintrag["b64_json"]:
        daten = base64.b64decode(eintrag["b64_json"])
        with open(datei, "wb") as f:
            f.write(daten)
        print("Bild gespeichert unter: %s (%d KB)" % (datei, len(daten) // 1024))
    elif "url" in eintrag and eintrag["url"]:
        # URL-Ausgabe: Datei mit kleinem Puffer herunterladen (schonend fuer 2 GB RAM)
        with urllib.request.urlopen(eintrag["url"], timeout=180) as quel:
            daten = quel.read()
        with open(datei, "wb") as f:
            f.write(daten)
        print("Bild gespeichert unter: %s (%d KB)" % (datei, len(daten) // 1024))
    else:
        raise SystemExit("Unerwartete API-Antwort: %s" % json.dumps(antwort)[:500])


def lokal_erzaehlen(thema, ausgabe_dir):
    """
    Fallback OHNE Internet: erzeugt eine kleine deutsche Geschichte aus einer
    lokalen Vorlage, damit das Programm auch ohne API-Key oder Netz laeuft.
    """
    geschichte = (
        "Es war einmal ein kleiner Roboter namens %s.\n"
        "Er lebte in einem alten Haus auf Linux Mint und traeumte davon, "
        "Geschichten zu erzaehlen.\n"
        "Eines Tages fand er eine Bluete im Garten und beschloss, sie zu malen.\n"
        "Und wenn er nicht gestorben ist, dann malt er noch heute.\n"
        "(Lokale Notgeschichte — bitte AGNES_API_KEY setzen fuer echte KI-Geschichten.)\n"
        % (thema or "Pixelino")
    )
    if not os.path.isdir(ausgabe_dir):
        os.makedirs(ausgabe_dir)
    datei = os.path.join(ausgabe_dir, "geschichte_lokal.txt")
    with open(datei, "w", encoding="utf-8") as f:
        f.write(geschichte)
    print("Lokale Geschichte (ohne KI) geschrieben nach: %s" % datei)


def main():
    parser = argparse.ArgumentParser(
        prog="agnes-client",
        description="Agnes-AI-Client fuer Texte und Bilder (Deutsch, Linux Mint 32-Bit)",
    )
    unter = parser.add_subparsers(dest="befehl")

    p_text = unter.add_parser("text", help="Text erzeugen (z. B. Geschichte auf Deutsch)")
    p_text.add_argument("--prompt", required=True, help="Auftrag an die KI (auf Deutsch)")
    p_text.add_argument("--system", default="", help="Optionale Systemanweisung")
    p_text.add_argument("--modell", default=TEXT_MODELLE[0], choices=TEXT_MODELLE)
    p_text.add_argument("--max-tokens", type=int, default=1200)
    p_text.add_argument("-o", "--ausgabe", default="", help="Zieldatei (sonst: Bildschirm)")

    p_bild = unter.add_parser("bild", help="Bild erzeugen")
    p_bild.add_argument("--prompt", required=True, help="Bildbeschreibung (auf Deutsch oder Englisch)")
    p_bild.add_argument("-o", "--out", default="bild.png")
    p_bild.add_argument("--modell", default=BILD_MODELLE[0], choices=BILD_MODELLE)
    p_bild.add_argument("--size", default="1024x768", choices=BILD_GROESSEN)

    p_gsch = unter.add_parser(
        "geschichte",
        help="Komfort: deutsche Geschichte ERZAEHLEN (text) UND BILD dazu erzeugen",
    )
    p_gsch.add_argument("thema", nargs="?", default="", help="Thema der Geschichte")
    p_gsch.add_argument("--ausgabe-dir", default="ausgaben", help="Ordner fuer Dateien")
    p_gsch.add_argument("--text-modell", default=TEXT_MODELLE[0], choices=TEXT_MODELLE)
    p_gsch.add_argument("--bild-modell", default=BILD_MODELLE[0], choices=BILD_MODELLE)

    args = parser.parse_args()

    if args.befehl == "text":
        inhalt = text_generieren(args.prompt, args.system, args.modell, args.max_tokens)
        if args.ausgabe:
            with open(args.ausgabe, "w", encoding="utf-8") as f:
                f.write(inhalt)
            print("Text geschrieben nach: %s" % args.ausgabe)
        else:
            print(inhalt)

    elif args.befehl == "bild":
        bild_generieren(args.prompt, args.out, args.modell, args.size)

    elif args.befehl == "geschichte":
        thema = args.thema or "Ein mutiger kleiner Igel im Wald"
        if not shutil.which("curl") or not os.environ.get("AGNES_API_KEY"):
            print("Kein API-Key gefunden — erzeuge lokale Notgeschichte.")
            lokal_erzaehlen(thema, args.ausgabe_dir)
            return
        system = (
            "Du bist ein freundlicher Geschichtenerzaehler. Antworte AUSSCHLIESSLICH "
            "auf Deutsch. Erzaehle eine kurze, kinderfreundliche Geschichte in etwa "
            "200–300 Woertern mit einfacher Sprache."
        )
        print("Erzeuge Geschichte (Modell: %s) …" % args.text_modell)
        geschichte = text_generieren(
            "Erzaehle eine schoene Geschichte ueber dieses Thema: %s" % thema,
            system, args.text_modell, 1200,
        )
        if not os.path.isdir(args.ausgabe_dir):
            os.makedirs(args.ausgabe_dir)
        text_pfad = os.path.join(args.ausgabe_dir, "geschichte.txt")
        with open(text_pfad, "w", encoding="utf-8") as f:
            f.write(geschichte)
        print("Geschichte gespeichert: %s" % text_pfad)

        # Bild-Prompt aus dem Thema ableiten
        woerter = re.sub(r"\W+", " ", thema).split()
        motiv = " ".join(woerter[:8]) or "Ein maechtiges Marchen"
        bild_prompt = (
            "Kinderbuch-Illustration im warmen Aquarellstil: %s. "
            "Freundlich, detailreich, keine Schrift im Bild." % motiv
        )
        print("Erzeuge passendes Bild (Modell: %s) …" % args.bild_modell)
        bild_generieren(bild_prompt, os.path.join(args.ausgabe_dir, "illustration.png"),
                        args.bild_modell, "1024x768")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
