"""
MWST-Berechnung (Konzeptdokument Abschnitt 9.4).

Schweizer Konsumentenpreise sind brutto (MWST inklusive). Der MWST-Betrag
wird daher aus dem Bruttobetrag zurückgerechnet, nicht aufgeschlagen.
"""
from decimal import ROUND_HALF_UP, Decimal


def mwst_betrag_aus_brutto(betrag_brutto: Decimal, satz_prozent: Decimal) -> Decimal:
    """
    Berechnet den in einem Bruttobetrag enthaltenen MWST-Anteil.

    Formel: mwst = betrag - betrag / (1 + satz/100)

    Bei satz_prozent == 0 (z.B. Mwstsatz.code == 'AUSGENOMMEN' für
    Kurtaxe/kantonale Beherbergungsabgabe, die keine MWST-Objekte sind)
    ist der MWST-Betrag 0.
    """
    if satz_prozent == 0:
        return Decimal("0.00")

    faktor = Decimal("1") + (satz_prozent / Decimal("100"))
    netto = betrag_brutto / faktor
    mwst = betrag_brutto - netto
    return mwst.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def gueltigen_mwstsatz_ermitteln(mwstsaetze: list, stichtag) -> "object | None":
    """
    Ermittelt aus einer Liste von Mwstsatz-Datensätzen (gleicher `code`,
    z.B. alle historischen Sätze für 'BEHERBERGUNG') denjenigen, der am
    gegebenen Stichtag (i.d.R. Leistungsdatum) gültig war.

    gueltig_bis == None bedeutet 'aktuell gültig / noch offen'.
    """
    for satz in mwstsaetze:
        if satz.gueltig_ab <= stichtag and (satz.gueltig_bis is None or stichtag <= satz.gueltig_bis):
            return satz
    return None
