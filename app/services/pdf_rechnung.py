"""
PDF der Rechnung (Konzeptdokument Abschnitt 12.1), erzeugt bei Bedarf aus den
gespeicherten Daten der Rechnung – nichts wird auf der Festplatte abgelegt.

Pflichtangaben für Schweizer Rechnungen: Absender mit MWST-Nummer, Empfänger,
Rechnungsnummer und -datum, Leistungszeitraum, Positionen mit MWST-Satz,
Aufschlüsselung der MWST je Satz. Taxen (Kurtaxe, Beherbergungsabgabe) sind
durchlaufende Posten ohne MWST.

Reines Layout: die Daten übergibt der Aufrufer (testbar ohne Datenbank).
"""
from dataclasses import dataclass, field
from decimal import Decimal
from io import BytesIO

from reportlab.lib.colors import HexColor, black
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

TIEFSEE = HexColor("#143040")
LEISE = HexColor("#56646b")
LINIE = HexColor("#d6dfe2")
NEBEL = HexColor("#eef2f3")


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
    kunde_zeilen: list[str]
    leistungszeitraum: str
    absender_zeilen: list[str]
    mwst_nummer: str = ""
    reservation: str = ""
    positionen: list[RechnungsPositionZeile] = field(default_factory=list)
    gesamtbetrag: Decimal = Decimal("0")
    anzahlung: Decimal = Decimal("0")
    anzahlung_text: str = "Anzahlung erhalten"
    zahlungsvermerk: str = ""
    """z.B. «Bezahlt am 11.11.2026, TWINT. Vielen Dank!» oder Zahlungsangaben bei offener Rechnung."""
    storniert: bool = False


def _chf(x: Decimal) -> str:
    return f"CHF {x:,.2f}".replace(",", "'")


def _menge(x: Decimal) -> str:
    return f"{x:.2f}".rstrip("0").rstrip(".")


def rechnung_pdf(daten: RechnungsDaten) -> bytes:
    puffer = BytesIO()
    c = canvas.Canvas(puffer, pagesize=A4)
    c.setTitle(f"Rechnung {daten.nummer}")
    breite, hoehe = A4
    rand = 50
    rechts = breite - rand

    def kopf():
        y = hoehe - 60
        c.setFillColor(TIEFSEE)
        c.setFont("Helvetica-Bold", 11)
        for i, zeile in enumerate(daten.absender_zeilen or ["Campingverwaltung"]):
            c.setFont("Helvetica-Bold" if i == 0 else "Helvetica", 11 if i == 0 else 9)
            c.drawString(rand, y, zeile)
            y -= 13
        if daten.mwst_nummer:
            c.setFont("Helvetica", 8.5)
            c.setFillColor(LEISE)
            c.drawString(rand, y - 2, daten.mwst_nummer)
            y -= 13
        return y

    y = kopf()
    # Empfänger (Fensterposition rechts)
    ye = hoehe - 150
    c.setFillColor(black)
    c.setFont("Helvetica", 10)
    for zeile in daten.kunde_zeilen:
        c.drawString(breite / 2 + 20, ye, zeile)
        ye -= 13
    y = min(y, ye) - 30

    c.setFont("Helvetica-Bold", 16)
    c.setFillColor(TIEFSEE)
    c.drawString(rand, y, f"Rechnung {daten.nummer}" + ("  – STORNIERT" if daten.storniert else ""))
    y -= 20
    c.setFont("Helvetica", 9.5)
    c.setFillColor(LEISE)
    angaben = [f"Datum: {daten.datum}", f"Aufenthalt: {daten.leistungszeitraum}"]
    if daten.reservation:
        angaben.append(f"Reservation: {daten.reservation}")
    c.drawString(rand, y, "   ·   ".join(angaben))
    y -= 26

    spalten = {"menge": rand + 300, "preis": rand + 370, "mwst": rand + 430}

    def tabellenkopf(y):
        c.setFillColor(NEBEL)
        c.rect(rand, y - 6, rechts - rand, 18, fill=1, stroke=0)
        c.setFillColor(LEISE)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(rand + 6, y, "Leistung")
        c.drawRightString(spalten["menge"], y, "Menge")
        c.drawRightString(spalten["preis"], y, "Preis")
        c.drawRightString(spalten["mwst"], y, "MWST")
        c.drawRightString(rechts - 6, y, "Betrag")
        return y - 20

    y = tabellenkopf(y)
    c.setFont("Helvetica", 9)
    for pos in daten.positionen:
        if y < 140:
            c.showPage()
            y = tabellenkopf(hoehe - 60)
            c.setFont("Helvetica", 9)
        c.setFillColor(black)
        text = pos.bezeichnung if len(pos.bezeichnung) <= 58 else pos.bezeichnung[:56] + "…"
        c.drawString(rand + 6, y, text)
        c.drawRightString(spalten["menge"], y, _menge(pos.menge))
        c.drawRightString(spalten["preis"], y, f"{pos.einzelpreis:.2f}")
        c.drawRightString(spalten["mwst"], y, f"{pos.mwstsatz_prozent:.1f}%" if pos.mwstsatz_prozent else "–")
        c.drawRightString(rechts - 6, y, f"{pos.betrag:.2f}")
        c.setStrokeColor(LINIE)
        c.line(rand, y - 6, rechts, y - 6)
        y -= 18

    y -= 8
    c.setFont("Helvetica-Bold", 10.5)
    c.drawString(spalten["preis"] - 60, y, "Total")
    c.drawRightString(rechts - 6, y, _chf(daten.gesamtbetrag))
    y -= 14
    c.setFont("Helvetica", 8.5)
    c.setFillColor(LEISE)
    saetze: dict[Decimal, list[Decimal]] = {}
    for pos in daten.positionen:
        if pos.mwstsatz_prozent > 0:
            mwst = pos.betrag - pos.betrag / (1 + pos.mwstsatz_prozent / 100)
            eintrag = saetze.setdefault(pos.mwstsatz_prozent, [Decimal("0"), Decimal("0")])
            eintrag[0] += pos.betrag
            eintrag[1] += mwst
    for satz, (basis, mwst) in sorted(saetze.items()):
        c.drawRightString(rechts - 6, y, f"inkl. MWST {satz:.1f}% auf {basis:.2f}: CHF {mwst:.2f}")
        y -= 11
    if any(p.mwstsatz_prozent == 0 for p in daten.positionen):
        c.drawRightString(rechts - 6, y, "Kurtaxe und Beherbergungsabgabe ohne MWST")
        y -= 11
    c.setFillColor(black)
    if daten.anzahlung:
        y -= 6
        c.setFont("Helvetica", 10)
        c.drawString(spalten["preis"] - 60, y, daten.anzahlung_text)
        c.drawRightString(rechts - 6, y, "– " + _chf(daten.anzahlung))
        y -= 16
        c.setFont("Helvetica-Bold", 11)
        c.drawString(spalten["preis"] - 60, y, "Restbetrag")
        c.drawRightString(rechts - 6, y, _chf(daten.gesamtbetrag - daten.anzahlung))
        y -= 8
    if daten.zahlungsvermerk:
        y -= 26
        c.setFont("Helvetica", 9.5)
        for zeile in daten.zahlungsvermerk.split("\n"):
            c.drawString(rand, y, zeile)
            y -= 13
    c.showPage()
    c.save()
    return puffer.getvalue()
