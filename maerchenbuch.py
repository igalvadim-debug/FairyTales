#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Maerchenbuch — das interaktive deutsche Maerchenbuch fuer den Linux-Rechner.

FRUEHER war dies als Firmware fuer ein ESP32-P4-Panel (Elecrow CrowPanel,
1024x600-Touchdisplay) geplant. Es gibt aber **keinen ESP mehr** — nur noch
einen Linux-Rechner. Dieses Programm ersetzt die komplette Firmware und laeuft
direkt unter Linux (X11/Wayland, Python 3.6+):

  * Deutsche Geschichten und Bilder erzeugt die Agnes-AI-API
    (https://github.com/AgnesAI-Labs/AgnesAI-Models). Ohne API-Key oder ohne
    Internet entsteht automatisch eine lokale Notgeschichte.
  * Vorlesen (TTS) in dieser Reihenfolge:
      1. Agnes-AI   POST /v1/audio/speech   (falls vom Endpunkt unterstuetzt)
      2. espeak-ng / espeak   (deutsche Stimme: sudo apt-get install espeak-ng)
      3. spd-say (speech-dispatcher), festival
      4. sonst: keine Sprachausgabe — der Text erscheint trotzdem
  * Alle Inhalte liegen auf der FESTPLATTE: ./maerchen/ (Standardordner,
    frei waehlbar mit --datenordner bzw. Umgebungsvariable MAERCHEN_ORDNER).
    Keine SD-Karte, kein Flashen, kein ESP, keine SPIFFS-Images.
  * Die alten Panel-Animationen (Buch auf/zu, Wisch, Vogel-Freund) werden durch
    Tastatur, Maus UND Touchscreen ersetzt: Klick = weiterblaettern,
    Pfeiltasten = vor/zurueck, 'v' = vorlesen, Esc = Stop.

Benutzung:
    python3 maerchenbuch.py                            # Fenster (GUI) starten
    python3 maerchenbuch.py --thema "Ein Igel"         # GUI, Thema schon eingegeben
    python3 maerchenbuch.py --neu "Ein tapferer Drache" --bild --vorlesen
    python3 maerchenbuch.py --liste                    # gespeicherte Maerchen
    python3 maerchenbuch.py --oeffnen 1 --vorlesen     # Maerchen Nr. 1 + Stimme
    python3 maerchenbuch.py --sprache                  # veruegbare Stimmen zeigen
    python3 maerchenbuch.py --hilfe

Es werden nur die Python-Standardbibliothek und Tkinter bentigt — ideal auch
fuer alte 32-Bit-Rechner mit nur 2 GB RAM.
"""

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

BASIS_URL = os.environ.get("AGNES_BASIS_URL", "https://apihub.agnes-ai.com/v1")
TEXT_MODELLE = ["agnes-2.5-flash", "agnes-2.0-flash", "agnes-1.5-flash"]
BILD_MODELLE = ["agnes-image-2.1-flash", "agnes-image-2.0-flash"]
BILD_GROESSEN = ["1024x768", "768x1024", "1024x1024", "1536x1024", "1024x1536"]

SKRIPTDIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATENORDNER = os.environ.get("MAERCHEN_ORDNER",
                                     os.path.join(SKRIPTDIR, "maerchen"))

SYSTEM_PROMPT = (
    "Du bist ein freundlicher Geschichtenerzaehler fuer Kinder. Antworte "
    "AUSSCHLIESSLICH auf Deutsch in einfacher, warmer Sprache. Erzaehle eine "
    "kurze, kinderfreundliche Geschichte in etwa 200-300 Woertern. Beginne "
    "in der ersten Zeile mit dem Titel in der Form: TITEL: <Titel>"
)


# --------------------------------------------------------------------------
#  Grundlagen: API-Key, Dateinamen
# --------------------------------------------------------------------------
def api_schluessel():
    """AGNES_API_KEY aus der Umgebung oder aus ~/.agnes_api_key (install.sh)."""
    schluessel = os.environ.get("AGNES_API_KEY", "").strip()
    if not schluessel:
        pfad = os.path.expanduser("~/.agnes_api_key")
        if os.path.isfile(pfad):
            try:
                with open(pfad, encoding="utf-8") as datei:
                    schluessel = datei.read().strip()
            except OSError:
                schluessel = ""
    return schluessel


def sicherer_name(text, standard="maerchen"):
    text = (text or "").strip().lower()
    for umlaut, ersatz in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        text = text.replace(umlaut, ersatz)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"[^a-z0-9_-]", "", text).strip("-_")
    return text[:48] or standard


def zeitstempel():
    return time.strftime("%Y%m%d-%H%M%S")


# --------------------------------------------------------------------------
#  Agnes-AI-Zugriff (nur Standardbibliothek — speicherschonend)
# --------------------------------------------------------------------------
def post_json(pfad, daten, timeout=180):
    anfrage = urllib.request.Request(
        BASIS_URL + pfad,
        data=json.dumps(daten).encode("utf-8"),
        headers={"Authorization": "Bearer " + api_schluessel(),
                 "Content-Type": "application/json"},
        method="POST")
    with urllib.request.urlopen(anfrage, timeout=timeout) as antwort:
        return json.loads(antwort.read().decode("utf-8"))


def text_generieren(prompt, system=SYSTEM_PROMPT, modell=None, max_tokens=1200):
    antwort = post_json("/chat/completions", {
        "model": modell or TEXT_MODELLE[0],
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": prompt}],
        "stream": False,
        "max_tokens": max_tokens})
    return antwort["choices"][0]["message"]["content"].strip()


def bild_generieren(prompt, ziel_pfad, modell=None, groesse="1024x768"):
    """Erzeugt ein Bild und schreibt es direkt auf die Festplatte."""
    antwort = post_json("/images/generations", {
        "model": modell or BILD_MODELLE[0],
        "prompt": prompt,
        "size": groesse,
        "response_format": "b64_json"})
    eintrag = antwort["data"][0]
    daten = b""
    if eintrag.get("b64_json"):
        daten = base64.b64decode(eintrag["b64_json"])
    elif eintrag.get("url"):
        with urllib.request.urlopen(eintrag["url"], timeout=180) as quel:
            daten = quel.read()
    if not daten:
        raise RuntimeError("Unerwartete API-Antwort: %s" % json.dumps(antwort)[:300])
    with open(ziel_pfad, "wb") as datei:
        datei.write(daten)
    return ziel_pfad


# --------------------------------------------------------------------------
#  Vorlesen (TTS) — von KI-Stimme bis System-Stimme
# --------------------------------------------------------------------------
def ki_sprachausgabe(text, wav_pfad):
    """Versucht die Agnes-AI-Sprachausgabe (OpenAI-kompatibel). True/False."""
    try:
        anfrage = urllib.request.Request(
            BASIS_URL + "/audio/speech",
            data=json.dumps({"model": "agnes-tts-1", "input": text,
                             "voice": "alloy"}).encode("utf-8"),
            headers={"Authorization": "Bearer " + api_schluessel(),
                     "Content-Type": "application/json"},
            method="POST")
        with urllib.request.urlopen(anfrage, timeout=180) as antwort:
            daten = antwort.read()
        if len(daten) > 1000:
            with open(wav_pfad, "wb") as datei:
                datei.write(daten)
            return True
    except Exception:
        pass
    return False


def audio_abspielen(pfad):
    """Spielt eine Datei mit dem besten veruegbaren Linux-Player ab."""
    moeglichkeiten = [
        ("mpv", ["mpv", "--no-video", "--really-quiet", pfad]),
        ("ffplay", ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", pfad]),
        ("aplay", ["aplay", "-q", pfad]),
        ("paplay", ["paplay", pfad]),
        ("cvlc", ["cvlc", "--play-and-exit", pfad])]
    for programm, befehl in moeglichkeiten:
        if shutil.which(programm):
            subprocess.run(befehl, check=False, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
            return True
    return False


def vorhandene_stimmen():
    """Lesbare Liste der TTS-Moeglichkeiten auf diesem Rechner."""
    funde = []
    if api_schluessel():
        funde.append("Agnes-AI (audio/speech)")
    if shutil.which("espeak-ng"):
        funde.append("espeak-ng")
    elif shutil.which("espeak"):
        funde.append("espeak")
    if shutil.which("spd-say"):
        funde.append("spd-say")
    if shutil.which("festival"):
        funde.append("festival")
    return funde


def vorlesen(text, wav_pfad=None):
    """Liest den Text laut vor. Gibt (erfolgreich, beschreibung) zurueck."""
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return False, "kein Text"

    # 1) KI-Stimme ueber die Agnes-AI-API (nur mit API-Key + Audio-Player)
    if api_schluessel() and wav_pfad and ki_sprachausgabe(text[:1500], wav_pfad):
        if audio_abspielen(wav_pfad):
            return True, "Agnes-AI-Stimme"

    # 2) espeak-ng / espeak mit deutscher Stimme
    for programm in ("espeak-ng", "espeak"):
        if shutil.which(programm):
            prozess = subprocess.run(
                [programm, "-v", "de", "-s", "145", "-p", "50", text[:4000]],
                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return prozess.returncode == 0, programm

    # 3) spd-say (Speech-Dispatcher — auf Linux Mint/Ubuntu meist vorhanden)
    if shutil.which("spd-say"):
        prozess = subprocess.run(["spd-say", "-l", "de", "-w", text[:4000]],
                                 check=False, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
        return prozess.returncode == 0, "spd-say"

    # 4) festival als letzte System-Stimme
    if shutil.which("festival"):
        prozess = subprocess.run(
            ["festival", "--tts"], input=text[:4000].encode("utf-8"),
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return prozess.returncode == 0, "festival"

    return False, ("keine Sprachausgabe gefunden — bitte installieren: "
                   "sudo apt-get install espeak-ng   (oder speech-dispatcher)")


# --------------------------------------------------------------------------
#  Lokale Notgeschichte (ohne Internet / ohne API-Key)
# --------------------------------------------------------------------------
_NOTGESCHICHTEN = [
    ("Der kleine Leuchtturm",
     "Es war einmal ein kleiner Leuchtturm am Rand eines grossen Hafens. Jeden "
     "Abend zündete er sein Licht, doch die grossen Schiffe sahen nur nach vorn. "
     "Eines Nachts zog dicker Nebel auf, und ein winziges Ruderboot fand den Weg "
     "nicht mehr. Der kleine Leuchtturm strahlte so hell er konnte, bis das Boot "
     "sicher im Hafen anlegte. Von da an warteten alle auf sein Licht - und der "
     "kleine Turm wusste: Auch Kleine koennen grosse Dinge tun."),
    ("Pixelino, der Kuechenroboter",
     "Pixelino war ein alter Kuechenroboter auf einem Linux-Rechner. Er konnte nur "
     "ein einziges Lied pfeifen, naemlich 'Haenseemann'. Eines Tages sollte im "
     "Kindergarten eine Auffuehrung stattfinden, und niemand wollte singen. "
     "Pixelino pfiff seine Melodie, die Kinder sangen mit - und am Ende klatschte "
     "der ganze Saal. Seitdem ist Pixelino der offizielle Hausmusiker."),
    ("Die mutige Laterne",
     "In einer stillen Strasse hing eine Laterne, die Angst vor der Dunkelheit "
     "hatte. Ein Kind namens Mira sagte: 'Du leuchtest doch immer, wenn du dich "
     "traust.' In der naechsten Nacht wagte sich Mira allein zum Baecker, und die "
     "Laterne zündete sich - Schritt fuer Schritt - selbst an. Am Morgen "
     "strahlten beide: Mira und ihre Laterne."),
]


def lokale_geschichte(thema):
    """Erzeugt ohne Netz eine Geschichte; das Thema wird erzaehlerisch eingebaut."""
    titel, text = _NOTGESCHICHTEN[(sum(map(ord, thema or "")) or 1) % len(_NOTGESCHICHTEN)]
    zusatz = ("\n\nDein Wunschthema '%s' hat der Laterne extra Mut gemacht."
              % thema) if thema else ""
    return ("TITEL: %s\n\n%s%s\n\n(Lokale Notgeschichte ohne KI — bitte "
            "AGNES_API_KEY setzen fuer echte KI-Maerchen.)" % (titel, text, zusatz))


# --------------------------------------------------------------------------
#  Maerchen-Bibliothek auf der Festplatte (ersetzt SPIFFS/SD-Karte)
# --------------------------------------------------------------------------
class MaerchenBibliothek:
    def __init__(self, ordner):
        self.ordner = ordner
        os.makedirs(ordner, exist_ok=True)

    def speichere(self, titel, text, bilddatei=None):
        name = "%s_%s" % (sicherer_name(titel, "ohne-titel"), zeitstempel())
        ordner = os.path.join(self.ordner, name)
        os.makedirs(ordner, exist_ok=True)
        with open(os.path.join(ordner, "geschichte.md"), "w", encoding="utf-8") as datei:
            datei.write("# %s\n\n%s\n" % (titel, text))
        meta = {"titel": titel, "erstellt": time.strftime("%Y-%m-%d %H:%M"),
                "datei": "geschichte.md", "bild": None}
        if bilddatei and os.path.isfile(bilddatei):
            shutil.copy2(bilddatei, os.path.join(ordner, "illustration.png"))
            meta["bild"] = "illustration.png"
        with open(os.path.join(ordner, "meta.json"), "w", encoding="utf-8") as datei:
            json.dump(meta, datei, ensure_ascii=False, indent=2)
        return ordner

    def lade(self, ordner):
        try:
            with open(os.path.join(ordner, "meta.json"), encoding="utf-8") as datei:
                meta = json.load(datei)
        except (OSError, ValueError):
            meta = {"titel": os.path.basename(ordner)}
        text = ""
        text_pfad = os.path.join(ordner, meta.get("datei", "geschichte.md"))
        if os.path.isfile(text_pfad):
            with open(text_pfad, encoding="utf-8") as datei:
                text = datei.read()
        bild = meta.get("bild")
        return meta, text, (os.path.join(ordner, bild) if bild else None)

    def liste(self):
        return [os.path.join(self.ordner, name) for name in
                sorted(os.listdir(self.ordner), reverse=True)
                if os.path.isfile(os.path.join(self.ordner, name, "meta.json"))]

    def loesche(self, ordner):
        shutil.rmtree(ordner, ignore_errors=True)


def titel_und_inhalt(rohtext):
    """Trennt 'TITEL: ...' bzw. '# ...' vom Geschichtentext."""
    zeilen = [z.strip() for z in rohtext.splitlines() if z.strip()]
    titel, inhalt = "", rohtext
    if zeilen:
        erste = zeilen[0]
        if erste.upper().startswith("TITEL:"):
            titel = erste.split(":", 1)[1].strip(" \"'#*")
            inhalt = "\n".join(zeilen[1:])
        elif erste.startswith("#"):
            titel = erste.lstrip("# ").strip()
            inhalt = "\n".join(zeilen[1:])
    return (titel or "Ohne Titel"), (inhalt or rohtext)


def neue_geschichte_erzeugen(thema, datenordner=None, mit_bild=False,
                             meldung=lambda s: None):
    """KI-Geschichte (+ optional Bild) erzeugen und auf der Festplatte speichern."""
    bibliothek = MaerchenBibliothek(datenordner or DEFAULT_DATENORDNER)
    tema = (thema or "").strip() or "Ein mutiger kleiner Igel im Wald"

    if api_schluessel():
        try:
            meldung("Erzeuge Geschichte mit Agnes-AI ...")
            rohtext = text_generieren(
                "Erzaehle eine schoene Geschichte ueber dieses Thema: %s" % tema)
            quelle = "Agnes-AI"
        except Exception as fehler:
            meldung("KI nicht erreichbar (%s) — nehme lokale Notgeschichte." % fehler)
            rohtext = lokale_geschichte(tema)
            quelle = "lokal"
    else:
        meldung("Kein API-Key gefunden — erzeuge lokale Notgeschichte.")
        rohtext = lokale_geschichte(tema)
        quelle = "lokal"

    titel, inhalt = titel_und_inhalt(rohtext)

    bild_pfad = None
    if mit_bild and api_schluessel():
        motiv = " ".join(re.sub(r"\W+", " ", tema).split()[:8])
        try:
            meldung("Erzeuge passendes Bild ...")
            bild_pfad = bild_generieren(
                "Kinderbuch-Illustration im warmen Aquarellstil: %s. "
                "Freundlich, detailreich, keine Schrift im Bild." % motiv,
                os.path.join(bibliothek.ordner, ".temp_bild.png"))
        except Exception as fehler:
            meldung("Bild nicht moeglich (%s)." % fehler)

    ordner = bibliothek.speichere(titel, inhalt, bild_pfad)
    if bild_pfad and os.path.isfile(bild_pfad):
        os.remove(bild_pfad)
    meta, text, bild_im_ordner = bibliothek.lade(ordner)
    return {"titel": titel, "text": text, "bild": bild_im_ordner,
            "ordner": ordner, "quelle": quelle}


# --------------------------------------------------------------------------
#  Grafische Oberflaeche (Tkinter) — ersetzt das 1024x600-Touchdisplay
# --------------------------------------------------------------------------
def gui_starten(datenordner=None, auto_thema=None, auto_vorlesen=False):
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, scrolledtext
    except ImportError:
        print("FEHLER: Tkinter fehlt. Bitte installieren: "
              "sudo apt-get install python3-tk")
        sys.exit(1)

    bibliothek = MaerchenBibliothek(datenordner or DEFAULT_DATENORDNER)
    zustand = {"bild_pfad": None, "lauf": False}

    root = tk.Tk()
    root.title("Maerchenbuch — deutsches Geschichtbuch fuer Linux (ohne ESP)")
    root.geometry("980x640")
    root.minsize(640, 420)

    # ---- Kopfzeile -------------------------------------------------------
    kopf = tk.Frame(root, bg="#6b4f2c")
    kopf.pack(fill="x")
    tk.Label(kopf, text="Mein Maerchenbuch", bg="#6b4f2c", fg="white",
             font=("Sans", 17, "bold")).pack(side="left", padx=12, pady=8)
    tk.Label(kopf, text="laeuft auf Linux — kein ESP32-P4 mehr nötig",
             bg="#6b4f2c", fg="#f2dcc0", font=("Sans", 10)).pack(side="right", padx=12)

    # ---- Eingabe ---------------------------------------------------------
    oben = tk.Frame(root, padx=10, pady=8)
    oben.pack(fill="x")
    tk.Label(oben, text="Thema / Wunsch (auf Deutsch):",
             font=("Sans", 10)).pack(anchor="w")
    eingabe = tk.Entry(oben, font=("Sans", 12))
    eingabe.pack(fill="x", pady=(2, 6))
    eingabe.focus_set()

    # ---- Anzeige (das "Display") ----------------------------------------
    anzeige = scrolledtext.ScrolledText(root, wrap="word", font=("Sans", 12),
                                        bg="#fffaf0", fg="#2b2b2b")

    statusfeld = tk.Label(root, anchor="w", relief="sunken", padx=8, pady=3,
                          text="Bereit.")
    statusfeld.pack(fill="x", side="bottom")
    seitenanzeige = tk.Label(root, anchor="center", bg="#efe6d8", height=1)
    seitenanzeige.pack(fill="x", side="bottom")

    buttons = {}

    def status(text):
        root.after(0, lambda: statusfeld.config(text=text))

    # ---- Buch-Navigation (wie frueher book_open/swipe/close am Panel) ----
    aktuelle_seite = [0]
    seiten = []

    def seite_zeigen(index):
        if not seiten:
            return
        index = max(0, min(index, len(seiten) - 1))
        aktuelle_seite[0] = index
        anzeige.config(state="normal")
        anzeige.delete("1.0", "end")
        anzeige.insert("1.0", seiten[index])
        anzeige.config(state="disabled")
        seitenanzeige.config(text="Seite %d von %d" % (index + 1, len(seiten)))

    def in_seiten_aufteilen(text):
        absaetze = [a.strip() for a in re.split(r"\n\s*\n", text) if a.strip()]
        if not absaetze:
            absaetze = [text]
        pro_seite = max(1, len(absaetze) // 4)
        seiten[:] = ["\n\n".join(absaetze[i:i + pro_seite])
                     for i in range(0, len(absaetze), pro_seite)]

    # ---- Aktionen --------------------------------------------------------
    def freigeben():
        for name, knopf in buttons.items():
            knopf.config(state="normal" if name != "stop" else "disabled")

    def blockieren():
        for name, knopf in buttons.items():
            knopf.config(state="disabled" if name != "stop" else "normal")

    def erzeugen():
        if zustand["lauf"]:
            return
        tema = eingabe.get().strip()
        zustand["lauf"] = True
        blockieren()
        status("Erzeuge neues Maerchen ...")

        def hintergrund():
            try:
                ergebnis = neue_geschichte_erzeugen(tema, bibliothek.ordner,
                                                   mit_bild=True, meldung=status)
                in_seiten_aufteilen(ergebnis["text"])
                zustand["bild_pfad"] = ergebnis["bild"]
                root.after(0, lambda: (seite_zeigen(0),
                                       status("Fertig: %s — gespeichert in %s"
                                              % (ergebnis["titel"], ergebnis["ordner"]))))
                if auto_vorlesen:
                    root.after(600, vorlesen_starten)
            except Exception as fehler:
                root.after(0, lambda: status("Fehler: %s" % fehler))
            finally:
                zustand["lauf"] = False
                root.after(0, freigeben)

        threading.Thread(target=hintergrund, daemon=True).start()

    def maerchen_offnen():
        eintraege = bibliothek.liste()
        if not eintraege:
            messagebox.showinfo("Keine Maerchen",
                                "Noch nichts gespeichert. Klicke auf 'Neues Maerchen'.")
            return
        fenster = tk.Toplevel(root)
        fenster.title("Gespeicherte Maerchen")
        liste = tk.Listbox(fenster, font=("Sans", 11), width=72, height=14)
        liste.pack(fill="both", expand=True, padx=8, pady=8)
        for ordner in eintraege:
            meta, _, _ = bibliothek.lade(ordner)
            liste.insert("end", "%s   (%s)" % (meta.get("titel", "?"),
                                               meta.get("erstellt", "")))
        liste.selection_set(0)

        def laden(event=None):
            idx = liste.curselection()
            if not idx:
                return
            meta, text, bild = bibliothek.lade(eintraege[idx[0]])
            in_seiten_aufteilen(text)
            zustand["bild_pfad"] = bild
            seite_zeigen(0)
            status("Geoeffnet: %s" % meta.get("titel", ""))
            fenster.destroy()

        tk.Button(fenster, text="Oeffnen", command=laden).pack(pady=(0, 8))
        liste.bind("<Double-1>", laden)

    def vorlesen_starten():
        if not seiten:
            status("Bitte zuerst ein Maerchen erzeugen oder oeffnen.")
            return
        text = "\n\n".join(seiten)
        status("Beginne Vorlesen ...")

        def hintergrund():
            ok, info = vorlesen(text, os.path.join(bibliothek.ordner, ".vorlese.wav"))
            root.after(0, lambda: status(("Vorlesen ueber: " if ok else
                                          "Sprachausgabe fehlgeschlagen: ") + info))
        threading.Thread(target=hintergrund, daemon=True).start()

    def stopp():
        for programm in ("espeak-ng", "espeak", "spd-say", "mpv", "ffplay"):
            if shutil.which("pkill"):
                subprocess.run(["pkill", "-f", programm], check=False,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        status("Vorlesen gestoppt.")

    def vorherige_seite(event=None):
        seite_zeigen(aktuelle_seite[0] - 1)

    def naechste_seite(event=None):
        seite_zeigen(aktuelle_seite[0] + 1)

    def speichern_unter():
        if not seiten:
            messagebox.showinfo("Nichts zu speichern", "Kein Maerchen vorhanden.")
            return
        pfad = filedialog.asksaveasfilename(defaultextension=".txt",
                                            initialfile="maerchen.txt",
                                            filetypes=[("Textdatei", "*.txt")])
        if pfad:
            with open(pfad, "w", encoding="utf-8") as datei:
                datei.write("\n\n".join(seiten))
            status("Gespeichert: %s" % pfad)

    def bild_anzeigen():
        pfad = zustand["bild_pfad"]
        if not pfad or not os.path.isfile(pfad):
            messagebox.showinfo("Kein Bild", "Zu diesem Maerchen gibt es kein Bild.")
            return
        try:
            from PIL import Image, ImageTk
            fenster = tk.Toplevel(root)
            fenster.title("Illustration")
            bild = Image.open(pfad)
            bild.thumbnail((760, 560))
            foto = ImageTk.PhotoImage(bild)
            label = tk.Label(fenster, image=foto)
            label.image = foto          # Referenz behalten!
            label.pack(padx=6, pady=6)
        except ImportError:
            subprocess.Popen(["xdg-open", pfad])
            status("Bild mit xdg-open geoeffnet: %s" % pfad)

    def letzten_loeschen():
        eintraege = bibliothek.liste()
        if not eintraege:
            status("Kein Maerchen zum Loeschen vorhanden.")
            return
        bibliothek.loesche(eintraege[0])
        status("Geloescht: %s" % os.path.basename(eintraege[0]))

    def hilfe():
        messagebox.showinfo(
            "Bedienung",
            "Neues Maerchen: Thema eintippen, dann Knopf druecken oder Enter.\n"
            "Blaettern: Pfeiltasten, Leertaste, Klick auf den Text (Touch erlaubt).\n"
            "Vorlesen: Taste 'v' oder Knopf — nutzt Agnes-AI, espeak-ng, spd-say "
            "oder festival.\n"
            "Alle Maerchen liegen als Ordner mit geschichte.md und "
            "illustration.png auf der Festplatte:\n%s\n"
            "Kein ESP, keine SD-Karte, kein Flashen." % bibliothek.ordner)

    # ---- Button-Leisten (Maus UND Touch) ---------------------------------
    def knopf(rahmen, name, text, aktion, bg="#d9b382"):
        kn = tk.Button(rahmen, text=text, command=aktion, font=("Sans", 11, "bold"),
                       bg=bg, relief="raised", bd=2, padx=10, pady=4)
        kn.pack(side="left", padx=3)
        buttons[name] = kn
        return kn

    leiste_haupt = tk.Frame(root, padx=8)
    klingen = vorhandene_stimmen()
    knopf(leiste_haupt, "neu", "Neues Maerchen", erzeugen, "#8fbf6f")
    knopf(leiste_haupt, "laden", "Maerchen oeffnen", maerchen_offnen)
    knopf(leiste_haupt, "vorlesen", "Vorlesen", vorlesen_starten, "#7fa8d9")
    buttons["stop"] = knopf(leiste_haupt, "stop", "Stop", stopp, "#d98c8c")
    buttons["stop"].config(state="disabled")

    anzeige.pack(fill="both", expand=True, padx=10, pady=(0, 4))

    leiste_blatt = tk.Frame(root)
    knopf(leiste_blatt, "zurueck", "< Zurueck", vorherige_seite)
    knopf(leiste_blatt, "vor", "Vor >", naechste_seite)
    knopf(leiste_blatt, "bild", "Bild anzeigen", bild_anzeigen, "#c9a0dc")

    leiste_datei = tk.Frame(root, padx=8)
    knopf(leiste_datei, "speichern", "Speichern unter ...", speichern_unter)
    knopf(leiste_datei, "loeschen", "Letzten loeschen", letzten_loeschen)
    tk.Button(leiste_datei, text="Hilfe", command=hilfe, font=("Sans", 11),
              padx=10, pady=4).pack(side="left", padx=3)

    leiste_haupt.pack(fill="x", pady=(0, 4))
    leiste_blatt.pack(fill="x", pady=(0, 4))
    leiste_datei.pack(fill="x", pady=(0, 6))

    anzeige.bind("<Button-1>", lambda e: naechste_seite())
    anzeige.bind("<Shift-Button-1>", vorherige_seite)
    anzeige.bind("<Button-4>", lambda e: vorherige_seite())
    anzeige.bind("<Button-5>", lambda e: naechste_seite())
    eingabe.bind("<Return>", lambda e: erzeugen())
    root.bind("<Left>", vorherige_seite)
    root.bind("<Right>", naechste_seite)
    root.bind("<space>", lambda e: naechste_seite())
    root.bind("<KeyPress-v>", lambda e: vorlesen_starten())
    root.bind("<Escape>", lambda e: stopp())

    anzeige.insert("1.0",
        "Willkommen im deutschen Maerchenbuch fuer deinen Linux-Rechner!\n\n"
        "Frueher war dies als Firmware fuer ein ESP32-P4-Panel gedacht — diesen\n"
        "ESP gibt es nicht mehr. Alles laeuft jetzt direkt hier auf dem Rechner:\n\n"
        "  -  Tippe oben ein Thema ein und klicke auf 'Neues Maerchen'.\n"
        "  -  Die Geschichte erscheint hier und wird auf der Festplatte\n"
        "     gespeichert: %s\n"
        "  -  'Vorlesen' erzaehlt das Maerchen laut. Vorhandene Stimmen: %s\n"
        "  -  Blaettern mit Pfeiltasten, Leertaste oder Klick auf den Text.\n\n"
        "Viel Spass!" % (bibliothek.ordner,
                        ", ".join(klingen) or "keine — apt install espeak-ng"))
    anzeige.config(state="disabled")
    seitenanzeige.config(text="Start")

    if auto_thema:
        eingabe.insert(0, auto_thema)
        root.after(300, erzeugen)

    root.mainloop()


# --------------------------------------------------------------------------
#  Kommandozeile (fur Skripte, Cronjobs und sehr schwache Rechner)
# --------------------------------------------------------------------------
def hauptprogramm():
    parser = argparse.ArgumentParser(
        prog="maerchenbuch",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Deutsches Maerchenbuch fuer Linux — ohne ESP32, ohne SD-Karte. "
                    "Geschichten/Bilder via Agnes-AI, Vorlesen via espeak-ng/spd-say/festival.",
        epilog='Beispiele:\n'
               '  python3 maerchenbuch.py\n'
               '  python3 maerchenbuch.py --neu "Ein tapferer Igel" --bild --vorlesen\n'
               '  python3 maerchenbuch.py --liste\n')
    parser.add_argument("--datenordner", default=DEFAULT_DATENORDNER,
                        help="Ordner auf der Festplatte (Standard: ./maerchen)")
    parser.add_argument("--neu", metavar="THEMA",
                        help="neue Geschichte sofort erzeugen (ohne GUI)")
    parser.add_argument("--bild", action="store_true",
                        help="zu --neu zusätzlich eine Illustration erzeugen")
    parser.add_argument("--thema", metavar="THEMA",
                        help="Thema fur den GUI-Start (wird dort gleich erzeugt)")
    parser.add_argument("--vorlesen", action="store_true",
                        help="nach dem Erzeugen/Start sofort laut vorlesen")
    parser.add_argument("--liste", action="store_true",
                        help="gespeicherte Maerchen anzeigen")
    parser.add_argument("--oeffnen", metavar="NUMMER", type=int,
                        help="gespeichertes Maerchen Nummer N auf der Konsole anzeigen")
    parser.add_argument("--sprache", action="store_true",
                        help="veruegbare Stimmen/TTS-Programme anzeigen")
    parser.add_argument("--hilfe", action="store_true", help="Kurzanleitung zeigen")
    args = parser.parse_args()

    bibliothek = MaerchenBibliothek(args.datenordner)

    if args.hilfe:
        print(__doc__)
        return

    if args.sprache:
        funde = vorhandene_stimmen()
        print("Vorlesen moeglich mit:",
              ", ".join(funde) if funde else
              "nichts installiert. Empfohlen: sudo apt-get install espeak-ng")
        return

    if args.liste:
        eintraege = bibliothek.liste()
        if not eintraege:
            print("Keine gespeicherten Maerchen in %s" % bibliothek.ordner)
            return
        print("Maerchen in %s:" % bibliothek.ordner)
        for nr, ordner in enumerate(eintraege, 1):
            meta, _, _ = bibliothek.lade(ordner)
            print("  %2d. %-38s %s %s" % (nr, meta.get("titel", "?"),
                                          meta.get("erstellt", ""),
                                          "(mit Bild)" if meta.get("bild") else ""))
        return

    if args.oeffnen is not None:
        eintraege = bibliothek.liste()
        if not 1 <= args.oeffnen <= len(eintraege):
            raise SystemExit("Nummer ausserhalb des Bereichs (1..%d)." % len(eintraege))
        meta, text, _ = bibliothek.lade(eintraege[args.oeffnen - 1])
        print("\n=== %s ===\n%s" % (meta.get("titel", ""), text))
        if args.vorlesen:
            ok, info = vorlesen(text, os.path.join(bibliothek.ordner, ".vorlese.wav"))
            print("[Vorlesen: %s]" % info)
        return

    if args.neu:
        ergebnis = neue_geschichte_erzeugen(args.neu, bibliothek.ordner,
                                           mit_bild=args.bild, meldung=print)
        print("\n=== %s ===\n%s\n[gespeichert in: %s]"
              % (ergebnis["titel"], ergebnis["text"], ergebnis["ordner"]))
        if args.vorlesen:
            ok, info = vorlesen(ergebnis["text"],
                                os.path.join(bibliothek.ordner, ".vorlese.wav"))
            print("[Vorlesen: %s]" % info)
        return

    gui_starten(bibliothek.ordner, auto_thema=args.thema, auto_vorlesen=args.vorlesen)


if __name__ == "__main__":
    hauptprogramm()
