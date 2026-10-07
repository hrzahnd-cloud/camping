"""
HESTA-Monatsmeldung: Bericht zusammenstellen, als PDF/CSV ausgeben und
als E-Mail an das BFS vorbereiten (Konzept Abschnitt 6).

Stand der BFS-Anbindung (geprüft auf bfs.admin.ch, "Digitale Eingabe der
Anzahl Logiernächte"): Es gibt keine offene Web-API. Die "PMS-Schnittstelle"
liest die Zahlen aus der Software und schickt sie per E-Mail an
hotelstatistik@bfs.admin.ch; dafür braucht der Betrieb eine BUR-Nummer vom
BFS. Das genaue Dateiformat ist öffentlich nicht dokumentiert. Darum liefert
dieses Modul (1) ein PDF als vollwertigen Weg für die manuelle Meldung und
(2) einen E-Mail-Versand mit PDF + CSV, der erst nach Rückfrage beim BFS
(Format, Freischaltung) aktiviert werden soll (HESTA_EMAIL_VERSAND_AKTIV).
"""
import csv
import io
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from email.message import EmailMessage

from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.services.hesta import HestaPosition

DARK = HexColor("#1f2d24")
ACCENT = HexColor("#3a6b4c")
ZEBRA = HexColor("#f4f6f4")
LINE = HexColor("#c9d2cc")

MONATE = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]

# Zeilen des internen HESTA-Formulars (docs/hesta_monatsmeldung.pdf); alles
# andere wird unter "Übrige Länder" zusammengefasst. Das CSV enthält jedes Land einzeln.
FORMULAR_LAENDER = [
    ("CH", "Schweiz"), ("DE", "Deutschland"), ("FR", "Frankreich"), ("NL", "Niederlande"),
    ("BE", "Belgien"), ("GB", "Vereinigtes Königreich"), ("AT", "Österreich"),
    ("IT", "Italien"), ("US", "USA"),
]


@dataclass
class HestaBericht:
    betrieb_name: str
    jahr: int
    monat: int
    positionen: list[HestaPosition]
    adresse: str = ""
    gemeinde: str = ""
    bur_nummer: str | None = None
    anzahl_zimmer: int | None = None
    anzahl_betten: int | None = None
    schliessungstage: list[tuple[date, date]] = field(default_factory=list)
    belegte_zimmer: int | None = None
    durchschnittsertrag: Decimal | None = None
    bemerkung: str = ""

    @property
    def total_personen(self) -> int:
        return sum(p.anzahl_personen for p in self.positionen)

    @property
    def total_uebernachtungen(self) -> int:
        return sum(p.anzahl_uebernachtungen for p in self.positionen)

    @property
    def meldemonat(self) -> str:
        return f"{MONATE[self.monat - 1]} {self.jahr}"

    def warnungen(self) -> list[str]:
        """Punkte, die vor einer Meldung zu klären sind."""
        w = []
        if not self.bur_nummer:
            w.append("BUR-Nummer fehlt (beim BFS anfragen: hotelstatistik@bfs.admin.ch).")
        if self.anzahl_zimmer is None or self.anzahl_betten is None:
            w.append("Anzahl Zimmer/Betten fehlt (mit dem BFS klären, was für Camping zu melden ist).")
        if not self.positionen:
            w.append("Keine abgerechneten Aufenthalte im Meldemonat.")
        return w


def schliessungstage_zu_text(zeitraeume: list[tuple[date, date]]) -> str:
    return "\n".join(f"{von.isoformat()}/{bis.isoformat()}" for von, bis in zeitraeume)


def schliessungstage_aus_text(text: str | None) -> list[tuple[date, date]]:
    if not text:
        return []
    ergebnis = []
    for zeile in text.splitlines():
        if "/" in zeile:
            von, bis = zeile.strip().split("/", 1)
            ergebnis.append((date.fromisoformat(von), date.fromisoformat(bis)))
    return ergebnis


def _formular_zeilen(positionen: list[HestaPosition]) -> list[tuple[str, int, int]]:
    nach_land = {p.land: p for p in positionen}
    zeilen = []
    for code, name in FORMULAR_LAENDER:
        p = nach_land.pop(code, None)
        zeilen.append((name, p.anzahl_personen if p else 0, p.anzahl_uebernachtungen if p else 0))
    zeilen.append((
        "Übrige Länder",
        sum(p.anzahl_personen for p in nach_land.values()),
        sum(p.anzahl_uebernachtungen for p in nach_land.values()),
    ))
    return zeilen


def erzeuge_hesta_pdf(bericht: HestaBericht) -> bytes:
    puffer = io.BytesIO()
    c = canvas.Canvas(puffer, pagesize=A4)
    breite, hoehe = A4
    rand = 40

    c.setFillColor(DARK)
    c.rect(0, hoehe - 80, breite, 80, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(rand, hoehe - 36, "Monatsmeldung Beherbergungsstatistik (HESTA)")
    c.setFont("Helvetica", 9)
    c.drawString(rand, hoehe - 54, f"Meldemonat {bericht.meldemonat}  |  Bundesamt für Statistik, hotelstatistik@bfs.admin.ch")

    y = hoehe - 110
    c.setFillColor(DARK)

    def feld(x: float, ypos: float, titel: str, wert: str) -> None:
        c.setFont("Helvetica-Bold", 8)
        c.drawString(x, ypos, titel)
        c.setFont("Helvetica", 10)
        c.drawString(x, ypos - 14, wert or "-")

    feld(rand, y, "Betrieb", bericht.betrieb_name)
    feld(300, y, "BUR-Nummer (BFS-Identifikator)", bericht.bur_nummer or "")
    y -= 40
    feld(rand, y, "Adresse", bericht.adresse)
    feld(300, y, "Gemeinde", bericht.gemeinde)
    y -= 40
    feld(rand, y, "Anzahl Zimmer", "" if bericht.anzahl_zimmer is None else str(bericht.anzahl_zimmer))
    feld(180, y, "Anzahl Betten", "" if bericht.anzahl_betten is None else str(bericht.anzahl_betten))
    feld(300, y, "Belegte Zimmer im Monat", "" if bericht.belegte_zimmer is None else str(bericht.belegte_zimmer))
    ertrag = "" if bericht.durchschnittsertrag is None else f"CHF {bericht.durchschnittsertrag:.2f}"
    feld(440, y, "Ø Ertrag je Logiernacht", ertrag)
    y -= 44

    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(DARK)
    c.drawString(rand, y, "ANKÜNFTE UND LOGIERNÄCHTE NACH HERKUNFTSLAND")
    y -= 10
    c.setFillColor(ACCENT)
    c.rect(rand, y - 18, breite - 2 * rand, 18, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(rand + 8, y - 13, "Land")
    c.drawRightString(breite - rand - 150, y - 13, "Anzahl Personen")
    c.drawRightString(breite - rand - 8, y - 13, "Anzahl Übernachtungen")
    y -= 18

    for i, (name, personen, naechte) in enumerate(_formular_zeilen(bericht.positionen)):
        if i % 2 == 0:
            c.setFillColor(ZEBRA)
            c.rect(rand, y - 20, breite - 2 * rand, 20, fill=1, stroke=0)
        c.setFillColor(DARK)
        c.setFont("Helvetica", 10)
        c.drawString(rand + 8, y - 14, name)
        c.drawRightString(breite - rand - 150, y - 14, str(personen))
        c.drawRightString(breite - rand - 8, y - 14, str(naechte))
        y -= 20

    c.setFillColor(DARK)
    c.rect(rand, y - 22, breite - 2 * rand, 22, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(rand + 8, y - 15, "Total")
    c.drawRightString(breite - rand - 150, y - 15, str(bericht.total_personen))
    c.drawRightString(breite - rand - 8, y - 15, str(bericht.total_uebernachtungen))
    y -= 44

    c.setFillColor(DARK)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(rand, y, "SCHLIESSUNGSTAGE IM MELDEMONAT")
    c.setFont("Helvetica", 10)
    if bericht.schliessungstage:
        for von, bis in bericht.schliessungstage:
            y -= 14
            c.drawString(rand, y, f"{von.strftime('%d.%m.%Y')} bis {bis.strftime('%d.%m.%Y')}")
    else:
        y -= 14
        c.drawString(rand, y, "keine")
    y -= 30

    c.setFont("Helvetica-Bold", 9)
    c.drawString(rand, y, "BEMERKUNGEN")
    c.setFont("Helvetica", 10)
    for zeile in (bericht.bemerkung or "-").splitlines()[:6]:
        y -= 14
        c.drawString(rand, y, zeile[:110])

    c.setStrokeColor(LINE)
    c.line(rand, 120, 250, 120)
    c.line(300, 120, 520, 120)
    c.setFont("Helvetica", 8)
    c.drawString(rand, 108, "Ort, Datum")
    c.drawString(300, 108, "Unterschrift")

    c.setFont("Helvetica-Oblique", 7.5)
    c.drawString(rand, 50, "Automatisch aus den abgerechneten Aufenthalten erzeugt (Campingverwaltung). "
                           "Ersetzt nicht die offizielle Erhebung des BFS.")
    c.showPage()
    c.save()
    return puffer.getvalue()


def erzeuge_hesta_csv(bericht: HestaBericht) -> str:
    """Neutrale CSV-Datei mit allen Ländern einzeln (kein offizielles BFS-Format)."""
    ziel = io.StringIO()
    w = csv.writer(ziel, delimiter=";", lineterminator="\n")
    w.writerow(["bur_nummer", "jahr", "monat", "land", "anzahl_personen", "anzahl_uebernachtungen"])
    for p in bericht.positionen:
        w.writerow([bericht.bur_nummer or "", bericht.jahr, bericht.monat, p.land,
                    p.anzahl_personen, p.anzahl_uebernachtungen])
    return ziel.getvalue()


def erzeuge_hesta_mail(
    bericht: HestaBericht, absender: str, empfaenger: str, pdf: bytes, csv_text: str
) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = f"HESTA-Meldung {bericht.bur_nummer or ''} {bericht.monat:02d}/{bericht.jahr}".replace("  ", " ")
    msg["From"] = absender
    msg["To"] = empfaenger
    schliessung = "; ".join(f"{v.isoformat()} bis {b.isoformat()}" for v, b in bericht.schliessungstage) or "keine"
    msg.set_content(
        f"HESTA-Monatsmeldung {bericht.meldemonat}\n"
        f"Betrieb: {bericht.betrieb_name} (BUR-Nummer {bericht.bur_nummer})\n"
        f"Zimmer: {bericht.anzahl_zimmer}, Betten: {bericht.anzahl_betten}\n"
        f"Total Ankünfte: {bericht.total_personen}, Total Logiernächte: {bericht.total_uebernachtungen}\n"
        f"Schliessungstage: {schliessung}\n"
        "Die Aufteilung nach Herkunftsland steht im PDF und in der CSV-Datei im Anhang.\n"
    )
    dateiname = f"hesta_{bericht.jahr}-{bericht.monat:02d}"
    msg.add_attachment(pdf, maintype="application", subtype="pdf", filename=f"{dateiname}.pdf")
    msg.add_attachment(csv_text.encode("utf-8"), maintype="text", subtype="csv", filename=f"{dateiname}.csv")
    return msg


def bericht_als_dict(bericht: HestaBericht) -> dict:
    return {
        "betrieb": bericht.betrieb_name,
        "bur_nummer": bericht.bur_nummer,
        "jahr": bericht.jahr,
        "monat": bericht.monat,
        "positionen": [
            {"land": p.land, "anzahl_personen": p.anzahl_personen,
             "anzahl_uebernachtungen": p.anzahl_uebernachtungen}
            for p in bericht.positionen
        ],
        "total_personen": bericht.total_personen,
        "total_uebernachtungen": bericht.total_uebernachtungen,
        "warnungen": bericht.warnungen(),
    }


__all__ = [
    "HestaBericht", "erzeuge_hesta_pdf", "erzeuge_hesta_csv", "erzeuge_hesta_mail",
    "bericht_als_dict", "schliessungstage_zu_text", "schliessungstage_aus_text",
]
