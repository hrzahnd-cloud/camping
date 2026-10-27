"""
Module der Bedienoberfläche und ihre Standard-Einstellung.

Phase 1 (Stand Oktober 2026): sichtbar sind Reservationen, Gäste und die
Belegungsübersicht. Alle übrigen Module sind gebaut, aber standardmässig
ausgeschaltet und lassen sich unter "Einstellungen" einschalten.
"""
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.einstellungen import ModulEinstellung


@dataclass(frozen=True)
class Modul:
    code: str
    bezeichnung: str
    beschreibung: str
    standard_aktiv: bool
    umschaltbar: bool = True


MODULE: tuple[Modul, ...] = (
    Modul("reservationen", "Reservationen", "Anfragen erfassen, prüfen und bearbeiten", True, umschaltbar=False),
    Modul("belegung", "Belegung", "Übersicht nach Stellplatz-Typ mit Erwachsenen/Kindern", True, umschaltbar=False),
    Modul("gaeste", "Gäste", "Gästestamm erfassen und bearbeiten", True, umschaltbar=False),
    Modul("buchungen", "Buchungen & Aufenthalte", "Buchungen mit Stellplatz, Check-in/-out", False),
    Modul("artikel", "Artikel & Preise", "Artikelstamm, Saisonpreise, MWST", False),
    Modul("rechnungen", "Rechnungen", "Rechnungen inkl. Kurtaxe/Beherbergungsabgabe, PDF", False),
    Modul("auswertungen", "Auswertungen", "Umsatz nach Kunde, Monat, Artikel, Zahlungsart", False),
    Modul("hesta", "HESTA-Meldung", "Monatsmeldung an das BFS", False),
    Modul("feratel", "Feratel", "Meldeschein-Vorbereitung für Feratel", False),
)
MODULE_NACH_CODE = {m.code: m for m in MODULE}


def modulstatus(db: Session) -> list[dict]:
    gespeichert = {e.code: e.aktiv for e in db.execute(select(ModulEinstellung)).scalars()}
    ergebnis = []
    for m in MODULE:
        aktiv = True if not m.umschaltbar else gespeichert.get(m.code, m.standard_aktiv)
        ergebnis.append({
            "code": m.code,
            "bezeichnung": m.bezeichnung,
            "beschreibung": m.beschreibung,
            "aktiv": aktiv,
            "umschaltbar": m.umschaltbar,
        })
    return ergebnis


def modul_setzen(db: Session, code: str, aktiv: bool) -> None:
    eintrag = db.get(ModulEinstellung, code)
    if eintrag is None:
        db.add(ModulEinstellung(code=code, aktiv=aktiv))
    else:
        eintrag.aktiv = aktiv
    db.commit()
