"""
Belegung der Stellplätze je Nacht (Anreisetag zählt, Abreisetag nicht).

Gezählt werden – so festgelegt mit dem Betrieb (November 2026):
- akzeptierte Reservationen (Status «bezahlt_akzeptiert»), solange noch kein
  Aufenthalt erfasst ist;
- Aufenthalte (Buchungen, nicht storniert), mit oder ohne Reservation.
Abgelehnte, stornierte, nicht erschienene und offene Anfragen belegen keinen Platz.

Die Platzzahl (Standard 50) und die Meldegrenze (Standard 45) gelten für die
Stellplätze Zelt, Wohnwagen und Camper; Zwärgli und Spycher werden separat
gezählt. Beide Werte sind unter Einstellungen änderbar.
"""
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.buchung import Buchung
from app.models.einstellungen import AppEinstellung
from app.models.reservation import Reservationsanfrage

STELLPLATZ_TYPEN = ("zeltwiese", "wohnwagen", "camper")
"""Zählen gegen die Platzzahl; Zwärgli und Spycher nicht."""
AKZEPTIERT = "bezahlt_akzeptiert"

EINSTELLUNGEN = {
    "belegung_plaetze": ("Stellplätze (Zelt, Wohnwagen, Camper)", 50),
    "belegung_meldung_ab": ("Meldung ab belegten Plätzen pro Nacht", 45),
}


def einstellungen(db: Session) -> dict[str, int]:
    gespeichert = {e.schluessel: e.wert for e in db.execute(
        select(AppEinstellung).where(AppEinstellung.schluessel.in_(EINSTELLUNGEN))).scalars()}
    werte = {}
    for schluessel, (_, standard) in EINSTELLUNGEN.items():
        try:
            werte[schluessel] = int(gespeichert.get(schluessel) or standard)
        except ValueError:
            werte[schluessel] = standard
    return werte


def einstellungen_setzen(db: Session, werte: dict[str, int]) -> dict[str, int]:
    for schluessel, wert in werte.items():
        if schluessel not in EINSTELLUNGEN:
            continue
        eintrag = db.get(AppEinstellung, schluessel)
        if eintrag is None:
            db.add(AppEinstellung(schluessel=schluessel, wert=str(int(wert))))
        else:
            eintrag.wert = str(int(wert))
    db.commit()
    return einstellungen(db)


def belegende_reservationen(db: Session, von: date, bis: date) -> list[Reservationsanfrage]:
    """Akzeptierte Reservationen ohne Aufenthalt, die eine Nacht in [von, bis] berühren."""
    return list(db.execute(
        select(Reservationsanfrage).where(
            Reservationsanfrage.status == AKZEPTIERT,
            Reservationsanfrage.gewuenscht_von.is_not(None), Reservationsanfrage.gewuenscht_bis.is_not(None),
            Reservationsanfrage.gewuenscht_von <= bis, Reservationsanfrage.gewuenscht_bis > von,
        )
    ).scalars())


def belegende_aufenthalte(db: Session, von: date, bis: date) -> list[Buchung]:
    return list(db.execute(
        select(Buchung).where(Buchung.status != "storniert", Buchung.von <= bis, Buchung.bis > von)
    ).scalars())


def stellplaetze_je_nacht(db: Session, von: date, bis: date,
                          ohne_anfrage_id=None) -> dict[date, int]:
    """Belegte Stellplätze (Zelt/Wohnwagen/Camper) je Nacht von `von` bis und mit `bis`."""
    naechte = {von + timedelta(days=i): 0 for i in range((bis - von).days + 1)}
    perioden = [(a.gewuenscht_von, a.gewuenscht_bis) for a in belegende_reservationen(db, von, bis)
                if a.stellplatz_typ in STELLPLATZ_TYPEN and a.id != ohne_anfrage_id]
    perioden += [(b.von, b.bis) for b in belegende_aufenthalte(db, von, bis) if b.stellplatz_typ in STELLPLATZ_TYPEN]
    for start, ende in perioden:
        for d in naechte:
            if start <= d < ende:
                naechte[d] += 1
    return naechte


def hohe_belegung(db: Session, anfrage: Reservationsanfrage) -> list[dict]:
    """
    Nächte der Anfrage, in denen mit ihr die Meldegrenze erreicht wird
    (z.B. 45 von 50). Nur für Stellplätze und nur für noch nicht
    erledigte Anfragen.
    """
    if (anfrage.stellplatz_typ not in STELLPLATZ_TYPEN or not anfrage.gewuenscht_von or not anfrage.gewuenscht_bis
            or anfrage.gewuenscht_bis <= anfrage.gewuenscht_von
            or anfrage.status in ("abgelehnt", "storniert", "nicht_erschienen", "angereist")):
        return []
    werte = einstellungen(db)
    letzte_nacht = anfrage.gewuenscht_bis - timedelta(days=1)
    belegt = stellplaetze_je_nacht(db, anfrage.gewuenscht_von, letzte_nacht, ohne_anfrage_id=anfrage.id)
    return [{"datum": d, "belegt": n, "mit_dieser": n + 1, "plaetze": werte["belegung_plaetze"]}
            for d, n in belegt.items() if n + 1 >= werte["belegung_meldung_ab"]]
