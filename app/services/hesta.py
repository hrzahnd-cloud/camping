"""
HESTA-Aggregation (Konzeptdokument Abschnitt 6.2).

Aggregiert abgerechnete Aufenthalte eines Monats nach Herkunftsland:
- anzahl_personen: distinkte Gäste mit Aufenthaltsbeginn im Meldemonat
- anzahl_uebernachtungen: Summe der auf den Monat entfallenden Nächte

Hinweis (siehe Konzept Abschnitt 8, offener Punkt): Die exakte BFS-Regel
für monatsübergreifende Aufenthalte ist mit der HESTA-Wegleitung
abzugleichen. Diese Implementierung verwendet eine plausible, aber noch
zu verifizierende Näherung (anteilige Nächte je Kalendermonat).
"""
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.buchung import Aufenthalt
from app.models.rechnung import Rechnung


@dataclass
class HestaPosition:
    land: str
    anzahl_personen: int
    anzahl_uebernachtungen: int


def _naechte_im_monat(ankunft: date, abreise: date, jahr: int, monat: int) -> int:
    """
    Anzahl Nächte eines Aufenthalts, die auf den gegebenen Kalendermonat
    entfallen. Eine Nacht wird dem Monat ihres Start-Datums zugerechnet
    (z.B. die Nacht 31.07.->01.08. zählt als Juli-Nacht).
    """
    monatsanfang = date(jahr, monat, 1)
    if monat == 12:
        naechster_monatsanfang = date(jahr + 1, 1, 1)
    else:
        naechster_monatsanfang = date(jahr, monat + 1, 1)

    start = max(ankunft, monatsanfang)
    ende = min(abreise, naechster_monatsanfang)
    return max((ende - start).days, 0)


def aggregiere_hesta_monat(db: Session, jahr: int, monat: int) -> list[HestaPosition]:
    """
    Ermittelt für den gegebenen Monat alle abgerechneten Aufenthalte
    (nur Aufenthalte, deren Buchung eine bezahlte Rechnung hat) und
    gruppiert sie nach Land des Gastes.
    """
    ergebnisse: dict[str, HestaPosition] = {}

    aufenthalte = db.execute(
        select(Aufenthalt)
        .join(Aufenthalt.buchung)
        .join(Rechnung, Rechnung.buchung_id == Aufenthalt.buchung_id)
        .where(Rechnung.status == "bezahlt")
    ).scalars().all()

    for aufenthalt in aufenthalte:
        naechte_im_monat = _naechte_im_monat(aufenthalt.ankunft, aufenthalt.abreise, jahr, monat)
        if naechte_im_monat <= 0:
            continue

        land = (aufenthalt.gast.land or "XX").upper()
        if land not in ergebnisse:
            ergebnisse[land] = HestaPosition(land=land, anzahl_personen=0, anzahl_uebernachtungen=0)

        # "Ankunft" zählt im Monat des tatsächlichen Aufenthaltsbeginns
        if aufenthalt.ankunft.year == jahr and aufenthalt.ankunft.month == monat:
            ergebnisse[land].anzahl_personen += 1

        ergebnisse[land].anzahl_uebernachtungen += naechte_im_monat

    return sorted(ergebnisse.values(), key=lambda p: p.land)
