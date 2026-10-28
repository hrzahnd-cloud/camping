"""
MWST-Berechnung (Konzeptdokument Abschnitt 9.4).

Schweizer Konsumentenpreise sind brutto (MWST inklusive). Der MWST-Betrag
wird daher aus dem Bruttobetrag zurückgerechnet, nicht aufgeschlagen.
"""
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session


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


def satz_am(db: Session, code: str, stichtag: date):
    """Der am Stichtag gültige Mwstsatz-Datensatz für einen Code (z.B. BEHERBERGUNG)."""
    from app.models.artikel import Mwstsatz

    saetze = db.execute(select(Mwstsatz).where(Mwstsatz.code == code)).scalars().all()
    return gueltigen_mwstsatz_ermitteln(saetze, stichtag)


def prozent_fuer_artikel(db: Session, artikel, stichtag: date) -> Decimal:
    """
    MWST-Satz eines Artikels am Stichtag (Leistungsdatum). Der Artikel verweist
    auf einen Satz; massgebend ist aber dessen Code, damit ein später neu
    hinterlegter Satz (z.B. ab 1.1.2028) automatisch gilt.
    """
    satz = satz_am(db, artikel.mwstsatz.code, stichtag)
    if satz is None:
        raise ValueError(f"Kein MWST-Satz '{artikel.mwstsatz.code}' am {stichtag:%d.%m.%Y} hinterlegt")
    return Decimal(str(satz.satz_prozent))


def neuen_satz_hinterlegen(db: Session, code: str, satz_prozent: Decimal, gueltig_ab: date,
                           bezeichnung: str | None = None):
    """
    Legt einen neuen Satz ab `gueltig_ab` an. Der bisher offene Satz desselben
    Codes endet am Vortag. Bestehende Rechnungen bleiben unverändert, weil sie
    den Satz als Snapshot in der Position speichern.
    """
    from app.models.artikel import Mwstsatz

    saetze = db.execute(select(Mwstsatz).where(Mwstsatz.code == code).order_by(Mwstsatz.gueltig_ab)).scalars().all()
    if not saetze:
        raise ValueError(f"Unbekannter MWST-Code '{code}'")
    letzter = saetze[-1]
    if gueltig_ab <= letzter.gueltig_ab:
        raise ValueError(
            f"Der neue Satz muss nach dem {letzter.gueltig_ab:%d.%m.%Y} beginnen (Beginn des letzten Satzes)"
        )
    if letzter.gueltig_bis is None or letzter.gueltig_bis >= gueltig_ab:
        letzter.gueltig_bis = gueltig_ab - timedelta(days=1)
    neu = Mwstsatz(code=code, bezeichnung=bezeichnung or letzter.bezeichnung,
                   satz_prozent=satz_prozent, gueltig_ab=gueltig_ab, gueltig_bis=None)
    db.add(neu)
    db.commit()
    db.refresh(neu)
    return neu


def letzten_satz_entfernen(db: Session, satz_id) -> None:
    """
    Korrektur einer Fehleingabe: entfernt den jüngsten Satz eines Codes, solange
    er noch nicht gilt, und öffnet den vorherigen wieder.
    """
    from app.models.artikel import Mwstsatz

    satz = db.get(Mwstsatz, satz_id)
    if satz is None:
        raise LookupError("MWST-Satz nicht gefunden")
    saetze = db.execute(select(Mwstsatz).where(Mwstsatz.code == satz.code).order_by(Mwstsatz.gueltig_ab)).scalars().all()
    if saetze[-1].id != satz.id or len(saetze) < 2:
        raise ValueError("Nur der jüngste Satz kann entfernt werden, und mindestens ein Satz muss bleiben")
    if satz.gueltig_ab <= date.today():
        raise ValueError("Der Satz gilt bereits und kann nicht mehr entfernt werden")
    saetze[-2].gueltig_bis = None
    db.delete(satz)
    db.commit()
