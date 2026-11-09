"""
Rechnung aus einem Aufenthalt (bei der Abreise), so mit dem Betrieb festgelegt
(November 2026):

- Positionen aus den Leistungen des Aufenthalts, je Saison und Preis eine
  Zeile (Nächte × Anzahl), Zwärgli/Spycher mit den inbegriffenen 2 Personen,
  dazu Kurtaxe und Beherbergungsabgabe (ohne MWST).
- Die erhaltene Anzahlung wird als eigene Zeile abgezogen; offen bleibt der
  Restbetrag.
- Bezahlt wird meist bar oder mit TWINT direkt bei der Abreise; Kartenzahlung
  ist vorbereitet und unter Einstellungen einschaltbar. Ohne Zahlungsart
  bleibt die Rechnung offen.
- Nummer «JJJJ-1000» fortlaufend je Jahr (app/services/rechnungsnummer.py).
- Solange eine gültige Rechnung besteht, ist der Aufenthalt gesperrt; nach
  einem Storno (Nummer bleibt verbraucht) ist er wieder änderbar.

Die Rechnung ist eine Kopie: Texte, Preise und MWST-Sätze werden in den
Positionen gespeichert, spätere Preisänderungen verändern sie nicht.
"""
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.artikel import Artikel
from app.models.buchung import Buchung
from app.models.einstellungen import AppEinstellung
from app.models.rechnung import Rechnung, Rechnungsposition
from app.models.reservation import Zahlung
from app.services import leistungen as lst
from app.services import preise as pr
from app.services.mwst import mwst_betrag_aus_brutto, mwst_je_satz
from app.services.rechnungsnummer import naechste_rechnungsnummer

ZAHLUNGSARTEN = {"bar": "Bar", "twint": "TWINT", "karte": "Karte", "ueberweisung": "Überweisung"}
KARTE_SCHLUESSEL = "zahlung_karte_aktiv"
TAX_ARTIKEL = {"kurtaxe_gemeinde": "KURTAXE", "beherbergungsabgabe_kanton": "BEHERBERGUNGSABGABE"}


class RechnungFehler(ValueError):
    pass


def karte_aktiv(db: Session) -> bool:
    e = db.get(AppEinstellung, KARTE_SCHLUESSEL)
    return bool(e and e.wert == "1")


def karte_setzen(db: Session, aktiv: bool) -> bool:
    e = db.get(AppEinstellung, KARTE_SCHLUESSEL)
    if e is None:
        db.add(AppEinstellung(schluessel=KARTE_SCHLUESSEL, wert="1" if aktiv else "0"))
    else:
        e.wert = "1" if aktiv else "0"
    db.commit()
    return aktiv


def erlaubte_zahlungsarten(db: Session) -> list[str]:
    return [z for z in ZAHLUNGSARTEN if z != "karte" or karte_aktiv(db)]


def anzahlung_der_buchung(db: Session, b: Buchung) -> Decimal:
    if not b.reservationsanfrage_id:
        return Decimal("0.00")
    zahlungen = db.execute(select(Zahlung).where(
        Zahlung.bezug_typ == "reservationsanfrage", Zahlung.bezug_id == b.reservationsanfrage_id,
        Zahlung.status == "eingegangen")).scalars()
    return sum((Decimal(str(z.betrag)) for z in zahlungen), Decimal("0.00"))


def _kurz(d: date) -> str:
    return f"{d.day}.{d.month}."


def _art_code(art: str) -> str:
    return lst.ART[art].artikel_code if art in lst.ART else art.upper()


def erstellen(db: Session, b: Buchung, zahlungsart: str | None, heute: date | None = None) -> Rechnung:
    heute = heute or date.today()
    if b.status != "ausgecheckt":
        raise RechnungFehler("Die Rechnung entsteht bei der Abreise – zuerst die Abreise erfassen")
    if b.rechnung is not None:
        raise RechnungFehler(f"Für diesen Aufenthalt gibt es bereits die Rechnung {b.rechnung.nummer}")
    if zahlungsart is not None and zahlungsart not in erlaubte_zahlungsarten(db):
        raise RechnungFehler(f"Zahlungsart «{zahlungsart}» ist nicht freigeschaltet")
    berechnung = pr.berechne(db, b, _art_code)
    if berechnung.fehlende_preise:
        fehlend = [z.bezeichnung for z in berechnung.zeilen if z.naechte_ohne_preis]
        raise RechnungFehler("Für folgende Leistungen fehlt ein Preis (ausserhalb der Saison?): " + ", ".join(fehlend)
                             + ". Bitte unter «Artikel & Preise» ergänzen oder die Leistung anpassen.")
    artikel = {a.code: a for a in db.execute(select(Artikel)).scalars()}
    zeilen_je_id = {z.id: z for z in b.leistungen}

    rechnung = Rechnung(buchung_id=b.id, kunde_id=b.hauptgast_id, nummer=naechste_rechnungsnummer(db, heute.year),
                        datum=heute, status="offen", gesamtbetrag=Decimal("0"), mwst_betrag_total=Decimal("0"))
    db.add(rechnung)
    db.flush()
    positionen: list[Rechnungsposition] = []

    def position(code, text, menge, einzelpreis, betrag, prozent):
        a = artikel.get(code)
        if a is None:
            raise RechnungFehler(f"Artikel «{code}» fehlt in den Grunddaten")
        prozent = Decimal(str(prozent if prozent is not None else a.mwstsatz.satz_prozent))
        betrag = Decimal(betrag).quantize(Decimal("0.01"))
        positionen.append(Rechnungsposition(
            rechnung_id=rechnung.id, artikel_id=a.id, bezeichnung=text[:200], menge=Decimal(menge),
            einzelpreis=Decimal(einzelpreis), betrag=betrag, mwstsatz_prozent=prozent,
            mwst_betrag=mwst_betrag_aus_brutto(betrag, prozent), reihenfolge=len(positionen)))

    reihenfolge = [a.code for a in lst.ARTEN]
    for zp in sorted(berechnung.zeilen, key=lambda z: (reihenfolge.index(zeilen_je_id[z.leistung_id].art)
                                                        if zeilen_je_id[z.leistung_id].art in reihenfolge else 99,
                                                        zeilen_je_id[z.leistung_id].von)):
        z = zeilen_je_id[zp.leistung_id]
        basis = zp.bezeichnung
        if lst.ist_stueck(z.art):
            basis += f", {_kurz(z.von)}"
        elif (z.von, z.bis) != (b.von, b.bis):
            basis += f", {_kurz(z.von)}–{_kurz(z.bis)}"
        if z.bemerkung:
            basis += f" ({z.bemerkung})"
        for styp, preis, menge in zp.teile or [[None, Decimal("0.00"), lst.menge(z)]]:
            text = basis + (f", {pr.SAISON_NAMEN[styp]}" if styp in pr.SAISON_NAMEN and len(zp.teile) > 1 else "")
            if zp.hinweis and "inbegriffen" in zp.hinweis:
                text += f" – {zp.hinweis}"
            position(zp.artikel_code, text, menge, preis, preis * menge, zp.mwst_prozent)
    for ab in berechnung.abzuege:
        position(ab.artikel_code, ab.bezeichnung, 1, ab.betrag, ab.betrag, ab.mwst_prozent)
    for t in lst.taxen(db, b):
        einzel = (t.betrag / t.personennaechte).quantize(Decimal("0.01")) if t.personennaechte else Decimal("0.00")
        position(TAX_ARTIKEL[t.typ], t.bezeichnung, t.personennaechte, einzel, t.betrag, Decimal("0"))

    db.add_all(positionen)
    rechnung.gesamtbetrag = sum((p.betrag for p in positionen), Decimal("0.00"))
    rechnung.mwst_betrag_total = sum((m for _, m in mwst_je_satz((p.betrag, p.mwstsatz_prozent) for p in positionen).values()),
                                     Decimal("0.00"))
    rechnung.anzahlung = min(anzahlung_der_buchung(db, b), rechnung.gesamtbetrag) if rechnung.gesamtbetrag > 0 else Decimal("0.00")
    if zahlungsart or rechnung.restbetrag <= 0:
        bezahlen(db, rechnung, zahlungsart, heute, commit=False)
    db.commit()
    db.refresh(rechnung)
    return rechnung


def bezahlen(db: Session, r: Rechnung, zahlungsart: str | None, datum: date | None = None, commit: bool = True) -> Rechnung:
    """Restbetrag als bezahlt erfassen (Schlusszahlung als Zahlung zur Rechnung)."""
    if r.status == "storniert":
        raise RechnungFehler("Die Rechnung ist storniert")
    if r.status == "bezahlt":
        raise RechnungFehler("Die Rechnung ist bereits bezahlt")
    rest = r.restbetrag
    if rest > 0:
        if zahlungsart not in erlaubte_zahlungsarten(db):
            raise RechnungFehler("Bitte eine Zahlungsart wählen")
        db.add(Zahlung(bezug_typ="rechnung", bezug_id=r.id, betrag=rest, zahlungsart=zahlungsart, status="eingegangen",
                       referenz=r.nummer, eingegangen_am=datetime.combine(datum or date.today(), datetime.min.time(),
                                                                           tzinfo=timezone.utc)))
    r.status, r.zahlungsart, r.bezahlt_am = "bezahlt", zahlungsart if rest > 0 else None, datum or date.today()
    if commit:
        db.commit()
        db.refresh(r)
    return r


def stornieren(db: Session, r: Rechnung) -> Rechnung:
    """Rechnung stornieren: Nummer bleibt vergeben, Aufenthalt ist wieder änderbar."""
    if r.status == "storniert":
        raise RechnungFehler("Die Rechnung ist bereits storniert")
    for z in db.execute(select(Zahlung).where(Zahlung.bezug_typ == "rechnung", Zahlung.bezug_id == r.id)).scalars():
        z.status = "storniert"
    r.status, r.storniert_am = "storniert", datetime.now(timezone.utc)
    db.commit()
    db.refresh(r)
    return r
