"""
Vergabe der Rechnungsnummer (Konzeptdokument Abschnitt 12/14).

Format: '{jahr}-{laufnummer}', z.B. '2026-1000'. Der Zähler beginnt pro
Jahr bei 999, sodass die erste Rechnung des Jahres die Nummer 1000 erhält.

WICHTIG: Die Vergabe muss atomar erfolgen, damit bei gleichzeitiger
Rechnungsstellung (zwei Mitarbeitende gleichzeitig am Check-out) keine
Nummer doppelt vergeben wird. Dafür wird die Zeile im Rechnungsnummern-
zaehler per `SELECT ... FOR UPDATE` gesperrt, bis die Transaktion
committet ist.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.rechnung import Rechnungsnummernzaehler


def naechste_rechnungsnummer(db: Session, jahr: int) -> str:
    """
    Liefert die nächste freie Rechnungsnummer für das gegebene Jahr.

    Muss innerhalb derselben DB-Transaktion aufgerufen werden, in der
    auch die Rechnung gespeichert wird (kein separates Commit dazwischen),
    damit die Sperre bis zum Ende der Rechnungserstellung hält.
    """
    zaehler = db.execute(
        select(Rechnungsnummernzaehler)
        .where(Rechnungsnummernzaehler.jahr == jahr)
        .with_for_update()
    ).scalar_one_or_none()

    if zaehler is None:
        zaehler = Rechnungsnummernzaehler(jahr=jahr, letzte_vergebene_nummer=999)
        db.add(zaehler)
        db.flush()  # damit die Row existiert und für zukünftige Aufrufe sperrbar ist

    zaehler.letzte_vergebene_nummer += 1
    db.flush()

    return f"{jahr}-{zaehler.letzte_vergebene_nummer}"
