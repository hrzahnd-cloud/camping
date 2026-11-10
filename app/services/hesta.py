"""
HESTA-Aggregation (Beherbergungsstatistik des BFS), so mit dem Betrieb festgelegt
(November 2026):

- Gemeldet werden je Land die Ankünfte und die Übernachtungen (Logiernächte) des
  Monats. Als Land gilt die **Nationalität** des Hauptgastes (statt Wohnsitzland;
  entspricht bei den Gästen fast immer dem Wohnsitz), für alle Personen des
  Aufenthalts.
- Gezählt werden alle Personen inkl. Kinder und Kleinkinder, aus den Leistungen
  der Aufenthalte (eingecheckt und abgereist): Ankünfte = Personen in der ersten
  Nacht, im Monat der Anreise; Übernachtungen = Personennächte im Monat (eine
  Nacht zählt zum Monat ihres Datums, z.B. 31.7.→1.8. zum Juli).
- Sortiert nach dem deutschen Ländernamen.
- Gemeldet wird Anfang des Folgemonats.
"""
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.buchung import Buchung
from app.services import laender
from app.services.leistungen import personen_je_nacht


@dataclass
class HestaPosition:
    land: str
    anzahl_personen: int
    """Ankünfte (Personen)"""
    anzahl_uebernachtungen: int
    name: str = field(default="")

    def __post_init__(self):
        self.name = self.name or laender.name(self.land)


def aggregiere_hesta_monat(db: Session, jahr: int, monat: int) -> list[HestaPosition]:
    """Ankünfte und Übernachtungen je Nationalität für den Monat, alphabetisch nach Land."""
    anfang = date(jahr, monat, 1)
    ende = date(jahr + 1, 1, 1) if monat == 12 else date(jahr, monat + 1, 1)
    ergebnisse: dict[str, HestaPosition] = {}
    buchungen = db.execute(select(Buchung).where(Buchung.status.in_(("eingecheckt", "ausgecheckt")),
                                                 Buchung.von < ende, Buchung.bis > anfang)).scalars()
    for b in buchungen:
        gast = b.hauptgast
        land = ((gast.nationalitaet or gast.land) if gast else None) or "XX"
        land = land.upper()
        je_nacht = personen_je_nacht(b)
        pos = ergebnisse.setdefault(land, HestaPosition(land=land, anzahl_personen=0, anzahl_uebernachtungen=0))
        if anfang <= b.von < ende:
            pos.anzahl_personen += sum(je_nacht.get(b.von, (0, 0, 0)))
        pos.anzahl_uebernachtungen += sum(sum(v) for d, v in je_nacht.items() if anfang <= d < ende)
    return sorted((p for p in ergebnisse.values() if p.anzahl_personen or p.anzahl_uebernachtungen),
                  key=lambda p: laender.sortierschluessel(p.land))
