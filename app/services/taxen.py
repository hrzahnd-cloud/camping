"""
Kurtaxe und kantonale Beherbergungsabgabe (Konzeptdokument Abschnitt 9.2).

Für jede Übernachtung einer Person ab 16 Jahren fallen beide Abgaben an:
- Kurtaxe Gemeinde Aeschi: CHF 3.50 pro Person und Nacht (auch Camping);
  Kinder bis 15 Jahre sind befreit; erhoben wird sie von Personen ohne
  steuerrechtlichen Wohnsitz in der Gemeinde (Information Aeschi Tourismus,
  Dezember 2018, Sätze ab 1.1.2019).
- Beherbergungsabgabe Kanton Bern: CHF 1.00 pro Person und Nacht
  (Amt für Wirtschaft, Tourismus und Regionalentwicklung).

Die Sätze stehen in der Tabelle `taxensatz` (siehe app/seed.py), nicht im Code.
Gerechnet wird je Nacht mit dem Alter der Person in dieser Nacht und dem an
diesem Tag gültigen Satz; so stimmt es auch beim 16. Geburtstag während des
Aufenthalts und bei einer Satzänderung mitten im Aufenthalt.

Das Alter ergibt sich aus Gast.geburtsdatum. Fehlt es, wird die Person als
erwachsen behandelt (Abgabe fällig) und in `warnungen` gemeldet, damit das
Geburtsdatum vor der Rechnungsstellung ergänzt wird.

Offen (aus den Quellen nicht ersichtlich): ob die Beherbergungsabgabe bei
steuerrechtlichem Wohnsitz in Aeschi ebenfalls entfällt. Hier gilt
`Aufenthalt.taxpflichtig == False` nur für die Kurtaxe.
"""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.artikel import Taxensatz
from app.models.buchung import Aufenthalt, Buchung

ARTIKEL_CODE = {
    "kurtaxe_gemeinde": "KURTAXE",
    "beherbergungsabgabe_kanton": "BEHERBERGUNGSABGABE",
}
BEZEICHNUNG = {
    "kurtaxe_gemeinde": "Kurtaxe {ort}",
    "beherbergungsabgabe_kanton": "Beherbergungsabgabe Kanton {ort}",
}
# Kurtaxe gilt nur für Personen ohne steuerrechtlichen Wohnsitz in der Gemeinde.
NUR_BEI_TAXPFLICHT = {"kurtaxe_gemeinde"}


@dataclass
class TaxPosition:
    typ: str
    artikel_code: str
    bezeichnung: str
    personennaechte: int
    einzelpreis: Decimal
    betrag: Decimal


@dataclass
class TaxenErgebnis:
    positionen: list[TaxPosition] = field(default_factory=list)
    warnungen: list[str] = field(default_factory=list)

    @property
    def total(self) -> Decimal:
        return sum((p.betrag for p in self.positionen), Decimal("0.00"))


def alter_am(geburtsdatum: date, stichtag: date) -> int:
    jahre = stichtag.year - geburtsdatum.year
    if (stichtag.month, stichtag.day) < (geburtsdatum.month, geburtsdatum.day):
        jahre -= 1
    return jahre


def _satz_fuer(saetze: list[Taxensatz], typ: str, tag: date, alter: int) -> Taxensatz | None:
    for s in saetze:
        if s.typ != typ or s.gueltig_ab > tag or (s.gueltig_bis is not None and s.gueltig_bis < tag):
            continue
        if s.altersgruppe_von is not None and alter < s.altersgruppe_von:
            continue
        if s.altersgruppe_bis is not None and alter > s.altersgruppe_bis:
            continue
        return s
    return None


def berechne_taxen(aufenthalte: list[Aufenthalt], saetze: list[Taxensatz]) -> TaxenErgebnis:
    """Berechnet die Abgaben für die gegebenen Aufenthalte (reine Funktion, ohne DB-Zugriff)."""
    ergebnis = TaxenErgebnis()
    naechte: dict[int, tuple[Taxensatz, int]] = {}
    unbekanntes_alter: set[str] = set()

    for aufenthalt in aufenthalte:
        gast = aufenthalt.gast
        name = f"{gast.vorname} {gast.nachname}"
        if gast.geburtsdatum is None:
            unbekanntes_alter.add(name)
        tag = aufenthalt.ankunft
        while tag < aufenthalt.abreise:
            alter = alter_am(gast.geburtsdatum, tag) if gast.geburtsdatum else 99
            for typ in ARTIKEL_CODE:
                if typ in NUR_BEI_TAXPFLICHT and not aufenthalt.taxpflichtig:
                    continue
                satz = _satz_fuer(saetze, typ, tag, alter)
                if satz is not None:
                    schluessel = id(satz)
                    bisher = naechte.get(schluessel, (satz, 0))[1]
                    naechte[schluessel] = (satz, bisher + 1)
            tag += timedelta(days=1)

    for name in sorted(unbekanntes_alter):
        ergebnis.warnungen.append(f"Geburtsdatum fehlt für {name}: als erwachsen gerechnet.")

    nach_typ: dict[str, list[tuple[Taxensatz, int]]] = defaultdict(list)
    for satz, anzahl in naechte.values():
        nach_typ[satz.typ].append((satz, anzahl))

    for typ in ARTIKEL_CODE:
        for satz, anzahl in sorted(nach_typ.get(typ, []), key=lambda e: e[0].gueltig_ab):
            preis = Decimal(str(satz.betrag_pro_nacht))
            if preis == 0:
                continue
            ergebnis.positionen.append(TaxPosition(
                typ=typ,
                artikel_code=ARTIKEL_CODE[typ],
                bezeichnung=BEZEICHNUNG[typ].format(ort=satz.gemeinde_oder_kanton),
                personennaechte=anzahl,
                einzelpreis=preis,
                betrag=(preis * anzahl).quantize(Decimal("0.01")),
            ))
    return ergebnis


def berechne_taxen_fuer_buchung(db: Session, buchung: Buchung) -> TaxenErgebnis:
    saetze = list(db.execute(select(Taxensatz)).scalars().all())
    return berechne_taxen(list(buchung.aufenthalte), saetze)
