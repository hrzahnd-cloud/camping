"""
Feratel-Meldeschein: Daten für die Gästemeldung vorbereiten und prüfen.

Grundlage: "Anleitung feratel Deskline WebClient Einzelmitglied" (Thun-Thunersee
Tourismus, 3. März 2026). Dort erfasst der Vermieter jede Gästemeldung von Hand
im WebClient (https://webclient4.deskline.net/GRI). Von einer maschinellen
Schnittstelle steht darin nichts; die SOAP-Anbindung (feratel_client.py) bleibt
bis zur PMS-Partner-Freischaltung ein Platzhalter.

Dieses Modul liefert deshalb, was im WebClient einzutragen ist, und meldet,
welche Pflichtangaben noch fehlen:
- Hauptgast: Vor-/Nachname, Land, Nationalität, Strasse, PLZ, Ort, E-Mail
- Begleitpersonen: Vor-/Nachname (und Alter bei der Voranmeldung)
- An- und Abreisedatum, Personengruppe
Weitere Regeln aus der Anleitung: Gruppen ab 10 Personen gehören in einen
Gruppen-Meldeschein; die PanoramaCard gibt es für Gäste ab 6 Jahren; ein
Meldeschein kann nur von Thun-Thunersee Tourismus storniert werden.
"""
from dataclasses import dataclass, field
from datetime import date

from app.models.buchung import Buchung, Gast
from app.services.taxen import alter_am

GRUPPE_AB_PERSONEN = 10
PANORAMACARD_AB_ALTER = 6

_HAUPTGAST_PFLICHT = [
    ("vorname", "Vorname"), ("nachname", "Nachname"), ("land", "Land"),
    ("nationalitaet", "Nationalität"), ("strasse", "Strasse"),
    ("plz", "PLZ"), ("ort", "Ort"), ("email", "E-Mail"),
]


@dataclass
class MeldescheinPerson:
    vorname: str
    nachname: str
    alter: int | None
    land: str | None = None
    nationalitaet: str | None = None
    strasse: str | None = None
    plz: str | None = None
    ort: str | None = None
    email: str | None = None


@dataclass
class Meldeschein:
    buchung_id: str
    ankunft: date
    abreise: date
    hauptgast: MeldescheinPerson
    begleitpersonen: list[MeldescheinPerson] = field(default_factory=list)
    fehlende_angaben: list[str] = field(default_factory=list)
    hinweise: list[str] = field(default_factory=list)

    @property
    def anzahl_personen(self) -> int:
        return 1 + len(self.begleitpersonen)


def _person(gast: Gast, stichtag: date) -> MeldescheinPerson:
    return MeldescheinPerson(
        vorname=gast.vorname, nachname=gast.nachname,
        alter=alter_am(gast.geburtsdatum, stichtag) if gast.geburtsdatum else None,
        land=gast.land, nationalitaet=gast.nationalitaet, strasse=gast.strasse,
        plz=gast.plz, ort=gast.ort, email=gast.email,
    )


def baue_meldeschein(buchung: Buchung) -> Meldeschein:
    aufenthalte = list(buchung.aufenthalte)
    ankunft = min((a.ankunft for a in aufenthalte), default=buchung.von)
    abreise = max((a.abreise for a in aufenthalte), default=buchung.bis)

    hauptgast = buchung.hauptgast
    schein = Meldeschein(
        buchung_id=str(buchung.id), ankunft=ankunft, abreise=abreise,
        hauptgast=_person(hauptgast, ankunft),
    )
    for a in aufenthalte:
        if a.gast_id != hauptgast.id:
            schein.begleitpersonen.append(_person(a.gast, ankunft))

    for attribut, bezeichnung in _HAUPTGAST_PFLICHT:
        if not getattr(schein.hauptgast, attribut):
            schein.fehlende_angaben.append(f"Hauptgast: {bezeichnung}")
    for i, p in enumerate(schein.begleitpersonen, 1):
        if p.alter is None:
            schein.fehlende_angaben.append(f"Begleitperson {i} ({p.vorname} {p.nachname}): Alter/Geburtsdatum")

    schein.hinweise.append("Personengruppe im WebClient wählen (Auswahlwerte sind in der Anleitung nicht aufgeführt).")
    if schein.anzahl_personen >= GRUPPE_AB_PERSONEN:
        schein.hinweise.append("Ab 10 Personen: Meldeschein 'Reisegruppe' verwenden.")
    ohne_karte = [p for p in [schein.hauptgast, *schein.begleitpersonen]
                  if p.alter is not None and p.alter < PANORAMACARD_AB_ALTER]
    if ohne_karte:
        schein.hinweise.append(f"{len(ohne_karte)} Person(en) unter {PANORAMACARD_AB_ALTER} Jahren erhalten keine PanoramaCard.")
    schein.hinweise.append("Jede Person braucht für die PanoramaCard eine E-Mail-Adresse (oder die des Hauptgastes).")
    return schein
