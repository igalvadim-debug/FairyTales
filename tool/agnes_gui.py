#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agnes-KI Oberflaeche — kleines deutsches Fensterprogramm (Tkinter).

Tkinter ist auf Linux Mint bereits vorinstalliert (paket python3-tk) und
verbraucht nur etwa 30–50 MB RAM — ideal fuer 32-Bit-Rechner mit 2 GB RAM.

Das Programm erzeugt über die Agnes-AI-API:
  * Texte/Geschichten  (Modell: agnes-2.5-flash,   POST /v1/chat/completions)
  * Bilder             (Modell: agnes-image-2.1-flash, POST /v1/images/generations)

Die netzwerkaufrufe laufen in einem Hintergrundthread, damit das Fenster
reagierbar bleibt. Doku: https://github.com/AgnesAI-Labs/AgnesAI-Models
"""

import base64
import io
import json
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from urllib import error, request

BASIS_URL = "https://apihub.agnes-ai.com/v1"
TEXT_MODELLE = ["agnes-2.5-flash", "agnes-2.0-flash", "agnes-1.5-flash"]
BILD_MODELLE = ["agnes-image-2.1-flash", "agnes-image-2.0-flash"]
BILD_GROESSEN = ["1024x768", "768x1024", "1024x1024", "1280x720", "1536x1024"]


def api_schluessel():
    schluessel = os.environ.get("AGNES_API_KEY", "").strip()
    if not schluessel and os.path.isfile(os.path.expanduser("~/.agnes_api_key")):
        with open(os.path.expanduser("~/.agnes_api_key")) as f:
            schluessel = f.read().strip()
    return schluessel


def post_json(pfad, daten):
    anfrage = request.Request(
        BASIS_URL + pfad,
        data=json.dumps(daten).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + api_schluessel(),
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with request.urlopen(anfrage, timeout=180) as antwort:
        return json.loads(antwort.read().decode("utf-8"))


class AgnesFenster:
    def __init__(self, root):
        self.root = root
        root.title("Agnes-KI — Geschichten und Bilder (Deutsch)")
        root.geometry("760x560")
        root.minsize(600, 420)

        # Hinweis falls kein API-Key gesetzt ist
        if not api_schluessel():
            self.status("ACHTUNG: Kein API-Key gefunden! Bitte AGNES_API_KEY setzen "
                        "(https://platform.agnes-ai.com/).")

        oben = tk.Frame(root, padx=8, pady=6)
        oben.pack(fill="x")

        tk.Label(oben, text="Thema / Auftrag (auf Deutsch):").pack(anchor="w")
        self.eingabe = tk.Entry(oben, width=80)
        self.eingabe.pack(fill="x", pady=(2, 6))
        self.eingabe.focus_set()

        knopfleiste = tk.Frame(oben)
        knopfleiste.pack(fill="x")

        tk.Button(knopfe_leiste := knopfleiste, text="📖 Geschichte erzeugen",
                  command=self.geschichte).pack(side="left", padx=3)
        tk.Button(knopfe_leiste, text="🖼 Bild erzeugen",
                  command=self.bild).pack(side="left", padx=3)
        tk.Button(knopfe_leiste, text="💾 Speichern",
                  command=self.speichern).pack(side="left", padx=3)

        modelle = tk.Frame(root, padx=8)
        modelle.pack(fill="x")
        tk.Label(modelle, text="Textmodell:").pack(side="left")
        self.text_modell = tk.StringVar(value=TEXT_MODELLE[0])
        tk.OptionMenu(modelle, self.text_modell, *TEXT_MODELLE).pack(side="left", padx=(2, 12))
        tk.Label(modelle, text="Bildmodell:").pack(side="left")
        self.bild_modell = tk.StringVar(value=BILD_MODELLE[0])
        tk.OptionMenu(modelle, self.bild_modell, *BILD_MODELLE).pack(side="left", padx=(2, 12))
        tk.Label(modelle, text="Groesse:").pack(side="left")
        self.groesse = tk.StringVar(value="1024x768")
        tk.OptionMenu(modelle, self.groesse, *BILD_GROESSEN).pack(side="left", padx=2)

        self.ausgabe = scrolledtext.ScrolledText(root, wrap="word", font=("Sans", 11))
        self.ausgabe.pack(fill="both", expand=True, padx=8, pady=(4, 2))

        self.statusfeld = tk.Label(root, anchor="w", relief="sunken", padx=6,
                                   text="Bereit.")
        self.statusfeld.pack(fill="x", side="bottom")

        self.bilddaten = None  # zuletzt erzeugtes Bild als Bytes

    # ----- Status/Helfer -----
    def status(self, text):
        self.root.after(0, lambda: self.statusfeld.config(text=text))

    def zeige_text(self, text):
        def _zeige():
            self.ausgabe.delete("1.0", "end")
            self.ausgabe.insert("1.0", text)
        self.root.after(0, _zeige)

    def blockiert_melden(self, spaeter_aktiv):
        self.root.after(0, lambda: (self.status("Arbeite… bitte warten."),
                                    [b.config(state="disabled") for b in spaeter_aktiv]))

    def frei_melden(self, buttons):
        self.root.after(0, lambda: (self.status("Fertig."),
                                    [b.config(state="normal") for b in buttons]))

    # ----- Aktionen -----
    def geschichte(self):
        thema = self.eingabe.get().strip()
        if not thema:
            messagebox.showwarning("Eingabe fehlt", "Bitte zuerst ein Thema eingeben.")
            return
        if not api_schluessel():
            messagebox.showerror("Kein API-Key",
                                 "Bitte den Umgebungsvariablen AGNES_API_KEY setzen "
                                 "oder die Datei ~/.agnes_api_key anlegen.\n"
                                 "Kostenloser Schluessel: https://platform.agnes-ai.com/")
            return
        modell = self.text_modell.get()

        def im_hintergrund():
            try:
                antwort = post_json("/chat/completions", {
                    "model": modell,
                    "messages": [
                        {"role": "system", "content":
                         "Du bist ein freundlicher Geschichtenerzaehler. Antworte "
                         "AUSSCHLIESSLICH auf Deutsch in einfacher, kinderfreundlicher Sprache."},
                        {"role": "user", "content":
                         "Erzaehle eine schoene Geschichte (ca. 200–300 Woerter) "
                         "ueber dieses Thema: " + thema},
                    ],
                    "stream": False,
                    "max_tokens": 1200,
                })
                text = antwort["choices"][0]["message"]["content"]
                self.zeige_text(text)
                self.status("Geschichte fertig (%s)." % modell)
            except Exception as fehler:
                self.zeige_text("FEHLER: %s" % fehler)
                self.status("Fehlgeschlagen.")

        threading.Thread(target=im_hintergrund, daemon=True).start()
        self.status("Erzeuge Geschichte…")

    def bild(self):
        beschreibung = self.eingabe.get().strip()
        if not beschreibung:
            messagebox.showwarning("Eingabe fehlt", "Bitte zuerst eine Bildbeschreibung eingeben.")
            return
        if not api_schluessel():
            messagebox.showerror("Kein API-Key",
                                 "Bitte AGNES_API_KEY setzen (https://platform.agnes-ai.com/).")
            return
        modell = self.bild_modell.get()
        groesse = self.groesse.get()

        prompt = ("Kinderbuch-Illustration im warmen Aquarellstil: %s. "
                  "Freundlich, detailreich, keine Schrift im Bild." % beschreibung)

        def im_hintergrund():
            try:
                antwort = post_json("/images/generations", {
                    "model": modell,
                    "prompt": prompt,
                    "size": groesse,
                    "response_format": "b64_json",
                })
                eintrag = antwort["data"][0]
                daten = b""
                if eintrag.get("b64_json"):
                    daten = base64.b64decode(eintrag["b64_json"])
                elif eintrag.get("url"):
                    daten = request.urlopen(eintrag["url"], timeout=180).read()
                if not daten:
                    raise ValueError("Keine Bilddaten erhalten.")
                self.bilddaten = daten
                pfad = os.path.join(os.getcwd(), "agnes_bild.png")
                with open(pfad, "wb") as f:
                    f.write(daten)
                self.zeige_text(
                    "Bild erzeugt (%s, %s) und gespeichert unter:\n%s\n\n"
                    "Groesse: %d KB — Klicke 'Speichern', um es woanders abzulegen."
                    % (modell, groesse, pfad, len(daten) // 1024))
                self._zeige_bild_im_fenster(daten)
                self.status("Bild fertig.")
            except Exception as fehler:
                self.zeige_text("FEHLER: %s" % fehler)
                self.status("Fehlgeschlagen.")

        threading.Thread(target=im_hintergrund, daemon=True).start()
        self.status("Erzeuge Bild…")

    def _zeige_bild_im_fenster(self, daten):
        """Zeigt das Bild verkleinert an, wenn PIL vorhanden ist (optional)."""
        try:
            from PIL import Image, ImageTk  # noqa: F401  (nur wenn installiert)
            bild = Image.open(io.BytesIO(daten))
            bild.thumbnail((360, 260))
            foto = ImageTk.PhotoImage(bild)
            fenster = tk.Toplevel(self.root)
            fenster.title("Vorschau")
            label = tk.Label(fenster, image=foto)
            label.image = foto  # Referenz behalten!
            label.pack(padx=6, pady=6)
        except ImportError:
            pass  # Ohne PIL wird das Bild trotzdem als Datei gespeichert.

    def speichern(self):
        if not self.bilddaten:
            # Text speichern
            text = self.ausgabe.get("1.0", "end").strip()
            if not text:
                messagebox.showinfo("Nichts zu speichern", "Es ist nichts erzeugt worden.")
                return
            pfad = filedialog.asksaveasfilename(
                defaultextension=".txt", initialfile="geschichte.txt",
                filetypes=[("Textdatei", "*.txt")])
            if pfad:
                with open(pfad, "w", encoding="utf-8") as f:
                    f.write(text)
                self.status("Text gespeichert: %s" % pfad)
            return
        pfad = filedialog.asksaveasfilename(
            defaultextension=".png", initialfile="illustration.png",
            filetypes=[("PNG-Bild", "*.png")])
        if pfad:
            with open(pfad, "wb") as f:
                f.write(self.bilddaten)
            self.status("Bild gespeichert: %s" % pfad)


def main():
    root = tk.Tk()
    AgnesFenster(root)
    root.mainloop()


if __name__ == "__main__":
    main()
