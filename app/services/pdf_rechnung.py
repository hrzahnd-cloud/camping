"""
PDF-Erzeugung für Rechnungen (Konzeptdokument Abschnitt 12.1).

Enthält die für Schweizer Rechnungen üblichen Pflichtangaben:
Rechnungsnummer, Datum, Leistungszeitraum, Aufschlüsselung nach
MWST-Satz (gesetzlich vorgeschrieben bei mehreren Steuersätzen auf
einer Rechnung), Zahlungsinformationen.

Reines Layout/Rendering – die eigentlichen Daten (Rechnung,
Rechnungspositionen, Kunde) werden vom Aufrufer übergeben, damit
dieses Modul unabhängig von der DB-Session testbar bleibt.
"""
from dataclasses import dataclass, field
from decimal import Decimal

from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

DARK = HexColor("#1f2d24")
ACCENT = HexColor("#3a6b4c")
LIGHT_LINE = HexColor("#c9d2cc")


@dataclass
class RechnungsPositionZeile:
    bezeichnung: str
    menge: Decimal
    einzelpreis: Decimal
    betrag: Decimal
    mwstsatz_prozent: Decimal


@dataclass
class RechnungsDaten:
    nummer: str
    datum: str
    kunde_name: str
    kunde_adresse: str
    leistungszeitraum: str
    betrieb_name: str
    betrieb_adresse: str
    betrieb_mwst_nummer: str
    positionen: list[RechnungsPositionZeile] = field(default_factory=list)
    gesamtbetrag: Decimal = Decimal("0")
    zahlungshinweis: str = ""


def erzeuge_rechnung_pdf(daten: RechnungsDaten, ziel_pfad: str) -> str:
    """Rendert die Rechnung als PDF und gibt den Zielpfad zurück."""
    c = canvas.Canvas(ziel_pfad, pagesize=A4)
    width, height = A4
    margin = 40

    # Kopfbereich
    c.setFillColor(DARK)
    c.rect(0, height - 80, width, 80, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(margin, height - 38, f"Rechnung {daten.nummer}")
    c.setFont("Helvetica", 10)
    c.drawString(margin, height - 56, daten.betrieb_name)
    c.drawString(margin, height - 70, f"MWST-Nr.: {daten.betrieb_mwst_nummer}")

    y = height - 110
    c.setFillColor(black)
    c.setFont("Helvetica", 10)
    c.drawString(margin, y, daten.kunde_name)
    c.drawString(margin, y - 14, daten.kunde_adresse)

    c.drawRightString(width - margin, y, f"Datum: {daten.datum}")
    c.drawRightString(width - margin, y - 14, f"Leistungszeitraum: {daten.leistungszeitraum}")

    y -= 55

    # Tabellenkopf
    col_bez, col_menge, col_preis, col_mwst, col_betrag = (
        margin, margin + 240, margin + 300, margin + 370, width - margin
    )
    c.setFillColor(ACCENT)
    c.rect(margin, y - 18, width - 2 * margin, 20, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(col_bez + 6, y - 13, "Position")
    c.drawString(col_menge, y - 13, "Menge")
    c.drawString(col_preis, y - 13, "Einzelpreis")
    c.drawString(col_mwst, y - 13, "MWST")
    c.drawRightString(col_betrag, y - 13, "Betrag")
    y -= 24

    c.setFont("Helvetica", 9)
    for pos in daten.positionen:
        c.setFillColor(black)
        c.drawString(col_bez + 6, y - 12, pos.bezeichnung)
        c.drawString(col_menge, y - 12, str(pos.menge))
        c.drawString(col_preis, y - 12, f"CHF {pos.einzelpreis:.2f}")
        c.drawString(col_mwst, y - 12, f"{pos.mwstsatz_prozent:.1f}%")
        c.drawRightString(col_betrag, y - 12, f"CHF {pos.betrag:.2f}")
        c.setStrokeColor(LIGHT_LINE)
        c.line(margin, y - 18, width - margin, y - 18)
        y -= 20
        if y < 150:  # einfacher Seitenumbruch bei vielen Positionen
            c.showPage()
            y = height - 60

    y -= 15
    # MWST-Aufschlüsselung je Satz (gesetzlich vorgeschrieben)
    saetze: dict[Decimal, Decimal] = {}
    for pos in daten.positionen:
        if pos.mwstsatz_prozent > 0:
            netto_mwst = pos.betrag - pos.betrag / (1 + pos.mwstsatz_prozent / 100)
            saetze[pos.mwstsatz_prozent] = saetze.get(pos.mwstsatz_prozent, Decimal("0")) + netto_mwst

    c.setFont("Helvetica", 8.5)
    for satz, mwst_summe in sorted(saetze.items()):
        c.drawRightString(col_betrag, y, f"davon MWST {satz:.1f}%: CHF {mwst_summe:.2f}")
        y -= 12

    y -= 10
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(col_betrag, y, f"Total: CHF {daten.gesamtbetrag:.2f}")

    if daten.zahlungshinweis:
        y -= 30
        c.setFont("Helvetica", 9)
        c.drawString(margin, y, daten.zahlungshinweis)

    c.showPage()
    c.save()
    return ziel_pfad
