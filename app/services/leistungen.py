"""
Leistungen eines Aufenthalts (Buchung): wer und was wann auf dem Platz war.

Jede Zeile hat eine Art, eine Anzahl und einen Zeitraum [von, bis). Beim
Check-in entstehen Zeilen für Erwachsene, Kinder, Kleinkinder und den
Stellplatz über den ganzen Aufenthalt, bei Zelt/Wohnwagen/Camper zudem die
Umweltabgabe (pro Stellplatz und Nacht). Danach lässt sich alles anpassen:
- ganzer Aufenthalt verlängern/verkürzen: Zeilen ziehen mit (`zeitraum_setzen`);
- Abwesenheit: z.B. 2 von 4 Kindern zwei Nächte weg (`abwesenheit`);
- zusätzliche Personen oder ein zusätzliches Zelt für einen Teil des Aufenthalts:
  eigene Zeile mit eigenem Zeitraum.

Altersgruppen (mit dem Betrieb festgelegt, November 2026): Erwachsene ab 16,
Kinder 6–15 (ohne Kurtaxe), Kleinkinder 0–5 (gratis).

Taxen: Beherbergungsabgabe Kanton Bern für alle Erwachsenen, Kurtaxe Aeschi nur
für kurtaxepflichtige Erwachsene (nicht z.B. bei Wohnsitz in der Gemeinde).
Die Sätze kommen aus der Tabelle `taxensatz`.
"""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.artikel import Taxensatz
from app.models.buchung import Buchung, BuchungLeistung
from app.services.taxen import _satz_fuer


@dataclass(frozen=True)
class Art:
    code: str
    bezeichnung: str
    artikel_code: str
    gruppe: str
    """person | stellplatz | unterkunft | zusatz"""
    einheit: str = "pro_nacht"
    """pro_nacht (Anzahl × Nächte) | stueck (Anzahl)"""


ARTEN: tuple[Art, ...] = (
    Art("erwachsene", "Erwachsene (ab 16)", "ERWACHSENE", "person"),
    Art("kinder", "Kinder (6–15)", "KINDER", "person"),
    Art("kleinkinder", "Kleinkinder (0–5)", "KLEINKINDER", "person"),
    Art("zeltwiese", "Zelt", "ZELT", "stellplatz"),
    Art("wohnwagen", "Wohnwagen", "WOHNWAGEN", "stellplatz"),
    Art("camper", "Camper", "CAMPER", "stellplatz"),
    Art("zwaergli", "Zwärgli", "ZWAERGLI", "unterkunft"),
    Art("spycher", "Spycher", "SPYCHER", "unterkunft"),
    Art("strom", "Strom", "STROM", "zusatz"),
    Art("auto", "Auto", "AUTO", "zusatz"),
    Art("motorrad", "Motorrad", "MOTORRAD", "zusatz"),
    Art("umweltabgabe", "Umweltabgabe", "UMWELTABGABE", "zusatz"),
    Art("wassertank", "Wassertankfüllung", "WASSERTANK", "zusatz", "stueck"),
)
ART = {a.code: a for a in ARTEN}
PERSONEN = ("erwachsene", "kinder", "kleinkinder")
MIT_UMWELTABGABE = ("zeltwiese", "wohnwagen", "camper")
"""Umweltabgabe pro Stellplatz und Nacht (mit dem Betrieb festgelegt, November 2026);
ein Zusatzzelt auf demselben Platz zählt nicht als eigener Stellplatz, Zwärgli/Spycher ohne."""


def ist_stueck(art: str) -> bool:
    return ART[art].einheit == "stueck"


def menge(z: BuchungLeistung) -> int:
    """Abrechnungsmenge: Anzahl × Nächte bzw. Anzahl bei Stückleistungen."""
    return z.anzahl if ist_stueck(z.art) else z.anzahl * z.naechte


def grundzeilen(b: Buchung) -> list[BuchungLeistung]:
    """Zeilen beim Check-in: Personen und Stellplatz über den ganzen Aufenthalt."""
    zeilen = []
    for art, anzahl in (("erwachsene", b.anzahl_erwachsene), ("kinder", b.anzahl_kinder),
                        ("kleinkinder", b.anzahl_kleinkinder)):
        if anzahl:
            zeilen.append(BuchungLeistung(art=art, anzahl=anzahl, von=b.von, bis=b.bis, kurtaxepflichtig=True))
    if b.stellplatz_typ in ART:
        zeilen.append(BuchungLeistung(art=b.stellplatz_typ, anzahl=1, von=b.von, bis=b.bis))
    if b.stellplatz_typ in MIT_UMWELTABGABE:
        zeilen.append(BuchungLeistung(art="umweltabgabe", anzahl=1, von=b.von, bis=b.bis))
    return zeilen


def stellplatz_wechseln(b: Buchung, neuer_typ: str) -> None:
    """
    Anderer Stellplatz-Typ: Zeilen des bisherigen Typs übernehmen den neuen;
    die Umweltabgabe kommt dazu bzw. entfällt (nur Zelt, Wohnwagen, Camper).
    """
    alt = b.stellplatz_typ
    for z in b.leistungen:
        if z.art == alt:
            z.art = neuer_typ
    hat_abgabe = any(z.art == "umweltabgabe" for z in b.leistungen)
    if neuer_typ in MIT_UMWELTABGABE and alt not in MIT_UMWELTABGABE and not hat_abgabe:
        b.leistungen.append(BuchungLeistung(art="umweltabgabe", anzahl=1, von=b.von, bis=b.bis))
    if neuer_typ not in MIT_UMWELTABGABE and alt in MIT_UMWELTABGABE:
        for z in [z for z in b.leistungen if z.art == "umweltabgabe"]:
            b.leistungen.remove(z)
    b.stellplatz_typ = neuer_typ


def personen_je_nacht(b: Buchung) -> dict[date, tuple[int, int, int]]:
    """(Erwachsene, Kinder, Kleinkinder) je Nacht; ohne Zeilen aus den Zählern der Buchung."""
    naechte = [b.von + timedelta(days=i) for i in range(max(0, (b.bis - b.von).days))]
    if not any(z.art in PERSONEN for z in b.leistungen):
        return {d: (b.anzahl_erwachsene or 0, b.anzahl_kinder or 0, b.anzahl_kleinkinder or 0) for d in naechte}
    werte = {d: [0, 0, 0] for d in naechte}
    for z in b.leistungen:
        if z.art in PERSONEN:
            i = PERSONEN.index(z.art)
            for d in werte:
                if z.von <= d < z.bis:
                    werte[d][i] += z.anzahl
    return {d: tuple(v) for d, v in werte.items()}


def zaehler_nachfuehren(b: Buchung) -> None:
    """Personenzahl der Buchung = Höchststand über den Aufenthalt (für Listen und Belegung)."""
    pj = personen_je_nacht(b)
    if pj:
        b.anzahl_erwachsene, b.anzahl_kinder, b.anzahl_kleinkinder = (max(v[i] for v in pj.values()) for i in range(3))


def zeitraum_setzen(b: Buchung, von: date, bis: date) -> None:
    """
    Ganzen Aufenthalt verschieben, verlängern oder verkürzen: Zeilen, die am
    bisherigen Anfang/Ende lagen, ziehen mit; alles wird auf den neuen
    Zeitraum begrenzt, Zeilen ganz ausserhalb entfallen.
    """
    alt_von, alt_bis = b.von, b.bis
    for z in list(b.leistungen):
        if ist_stueck(z.art):
            if not von <= z.von < bis:
                b.leistungen.remove(z)
            continue
        if z.von == alt_von:
            z.von = von
        if z.bis == alt_bis:
            z.bis = bis
        z.von, z.bis = max(z.von, von), min(z.bis, bis)
        if z.bis <= z.von:
            b.leistungen.remove(z)
    b.von, b.bis = von, bis
    for a in b.aufenthalte:
        if a.gast_id == b.hauptgast_id:
            a.ankunft, a.abreise = von, bis
    zaehler_nachfuehren(b)


def abwesenheit(b: Buchung, z: BuchungLeistung, anzahl: int, von: date, bis: date) -> None:
    """
    `anzahl` aus Zeile `z` sind von `von` bis `bis` (Rückkehrtag) nicht da.
    Die Zeile wird aufgeteilt: die übrigen bleiben über den ganzen Zeitraum,
    die Abwesenden erhalten eine Zeile vor und eine nach der Abwesenheit.
    """
    if ist_stueck(z.art):
        raise ValueError("Bei Stückleistungen gibt es keine Abwesenheit")
    if not 1 <= anzahl <= z.anzahl:
        raise ValueError(f"Anzahl muss zwischen 1 und {z.anzahl} liegen")
    von, bis = max(von, z.von), min(bis, z.bis)
    if bis <= von:
        raise ValueError("Die Abwesenheit muss innerhalb des Zeitraums der Zeile liegen")
    teile = []
    if z.von < von:
        teile.append((z.von, von))
    if bis < z.bis:
        teile.append((bis, z.bis))
    for start, ende in teile:
        b.leistungen.append(BuchungLeistung(art=z.art, anzahl=anzahl, von=start, bis=ende,
                                            kurtaxepflichtig=z.kurtaxepflichtig, bemerkung=z.bemerkung))
    if anzahl == z.anzahl:
        b.leistungen.remove(z)
    else:
        z.anzahl -= anzahl
    zaehler_nachfuehren(b)


@dataclass
class TaxZeile:
    typ: str
    bezeichnung: str
    personennaechte: int
    betrag: Decimal


def taxen(db: Session, b: Buchung) -> list[TaxZeile]:
    """Kurtaxe (nur Pflichtige) und Beherbergungsabgabe (alle Erwachsenen) je Personennacht."""
    saetze = list(db.execute(select(Taxensatz)).scalars())
    summe: dict[str, list] = defaultdict(lambda: [0, Decimal("0.00"), None])
    for z in b.leistungen:
        if z.art != "erwachsene":
            continue
        tag = z.von
        while tag < z.bis:
            for typ in ("kurtaxe_gemeinde", "beherbergungsabgabe_kanton"):
                if typ == "kurtaxe_gemeinde" and not z.kurtaxepflichtig:
                    continue
                satz = _satz_fuer(saetze, typ, tag, 30)
                if satz is None:
                    continue
                eintrag = summe[typ]
                eintrag[0] += z.anzahl
                eintrag[1] += Decimal(str(satz.betrag_pro_nacht)) * z.anzahl
                eintrag[2] = satz.gemeinde_oder_kanton
            tag += timedelta(days=1)
    namen = {"kurtaxe_gemeinde": "Kurtaxe {}", "beherbergungsabgabe_kanton": "Beherbergungsabgabe Kanton {}"}
    return [TaxZeile(typ, namen[typ].format(summe[typ][2] or ""), summe[typ][0], summe[typ][1].quantize(Decimal("0.01")))
            for typ in ("kurtaxe_gemeinde", "beherbergungsabgabe_kanton") if typ in summe]
