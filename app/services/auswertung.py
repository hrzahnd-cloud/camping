"""
Auswertungen (Modul «Auswertungen»), so mit dem Betrieb festgelegt (November 2026):

1. Einnahmen und MWST pro Monat **nach vereinnahmtem Entgelt** (so rechnet der
   Betrieb mit der ESTV ab): massgebend ist der Zahlungseingang – Anzahlungen
   und Schlusszahlungen. Eine Zahlung zu einer abgerechneten Reservation wird
   im Verhältnis des Rechnungstotals aufgeteilt (MWST-pflichtiger Umsatz je
   Satz, durchlaufende Taxen). Anzahlungen ohne Rechnung (noch nicht
   abgereist, nicht erschienen) gelten vorläufig ganz als Beherbergung.
2. Übernachtungen pro Monat nach Nacht (Kontrolle zu Feratel): Personennächte
   Erwachsene/Kinder/Kleinkinder, Kurtaxe nur Pflichtige, Beherbergungsabgabe,
   Stellplatz-Nächte je Typ, Ankünfte.
3. Saison-Zusammenstellung für die Buchhaltung: Rechnungen des Jahres je
   Leistung, MWST je Satz auf den Rechnungstotalen, Taxen, Einnahmen je
   Zahlungsart, offene Rechnungen, Anzahlungen ohne Rechnung.

Vorjahresvergleich mit den Daten aus dem Tool (keine Erfassung früherer Jahre).
"""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.artikel import Taxensatz
from app.models.buchung import Buchung
from app.models.rechnung import Rechnung
from app.models.reservation import Reservationsanfrage, Zahlung
from app.services import leistungen as lst
from app.services.mwst import zahl_text, mwst_betrag_aus_brutto, satz_am
from app.services.taxen import _satz_fuer

NULL = Decimal("0.00")
MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]
ZAHLUNGSARTEN = {"bar": "Bar", "twint": "TWINT", "karte": "Karte", "kreditkarte": "Karte", "ueberweisung": "Überweisung",
                 "bankueberweisung": "Überweisung"}


def _r(x: Decimal) -> str:
    return str(Decimal(x).quantize(Decimal("0.01")))


def _zusammensetzung(r: Rechnung) -> tuple[dict[Decimal, Decimal], Decimal]:
    """(Brutto je MWST-Satz, Taxen) einer Rechnung."""
    je_satz: dict[Decimal, Decimal] = defaultdict(lambda: NULL)
    taxen = NULL
    for p in r.positionen:
        satz, betrag = Decimal(str(p.mwstsatz_prozent)), Decimal(str(p.betrag))
        if satz:
            je_satz[satz] += betrag
        else:
            taxen += betrag
    return dict(je_satz), taxen


def _rechnung_zur_anfrage(db: Session, anfrage_id) -> Rechnung | None:
    b = db.execute(select(Buchung).where(Buchung.reservationsanfrage_id == anfrage_id)).scalars().first()
    return b.rechnung if b else None


def zahlungen_im_jahr(db: Session, jahr: int) -> list[dict]:
    """Eingegangene Zahlungen des Jahres, aufgeteilt nach Satz und Taxen."""
    zahlungen = db.execute(select(Zahlung).where(Zahlung.status == "eingegangen")).scalars()
    beherbergung = {}
    ergebnis = []
    for z in zahlungen:
        if z.eingegangen_am is None or z.eingegangen_am.year != jahr:
            continue
        tag = z.eingegangen_am.date()
        betrag = Decimal(str(z.betrag))
        rechnung, art, gast, ref = None, "anzahlung", "", z.referenz
        if z.bezug_typ == "rechnung":
            rechnung = db.get(Rechnung, z.bezug_id)
            art = "schlusszahlung"
        else:
            rechnung = _rechnung_zur_anfrage(db, z.bezug_id)
            anfrage = db.get(Reservationsanfrage, z.bezug_id)
            gast, ref = (anfrage.gast_name, anfrage.nummer) if anfrage else ("", ref)
        if rechnung is not None and rechnung.status == "storniert":
            rechnung = None
        anteile: dict[Decimal, Decimal] = {}
        taxen = NULL
        if rechnung is not None and Decimal(str(rechnung.gesamtbetrag)) > 0:
            je_satz, tax = _zusammensetzung(rechnung)
            faktor = betrag / Decimal(str(rechnung.gesamtbetrag))
            anteile = {s: b * faktor for s, b in je_satz.items()}
            taxen = tax * faktor
            gast = gast or f"{rechnung.kunde.vorname} {rechnung.kunde.nachname}"
        else:
            if tag not in beherbergung:
                s = satz_am(db, "BEHERBERGUNG", tag)
                beherbergung[tag] = Decimal(str(s.satz_prozent)) if s else Decimal("0")
            anteile = {beherbergung[tag]: betrag} if beherbergung[tag] else {}
            if not beherbergung[tag]:
                taxen = betrag
        ergebnis.append({"datum": tag, "betrag": betrag, "zahlungsart": ZAHLUNGSARTEN.get(z.zahlungsart, z.zahlungsart),
                         "art": art, "vorlaeufig": rechnung is None, "anteile": anteile, "taxen": taxen,
                         "rechnung": rechnung.nummer if rechnung else None, "gast": gast, "referenz": ref})
    return sorted(ergebnis, key=lambda x: x["datum"])


def einnahmen(db: Session, jahr: int) -> dict:
    """Einnahmen und MWST pro Monat (vereinnahmt)."""
    monate = [{"monat": m, "name": MONATE[m - 1], "einnahmen": NULL, "taxen": NULL, "je_satz": defaultdict(lambda: NULL),
               "zahlungsarten": defaultdict(lambda: NULL), "vorlaeufig": NULL} for m in range(1, 13)]
    for z in zahlungen_im_jahr(db, jahr):
        m = monate[z["datum"].month - 1]
        m["einnahmen"] += z["betrag"]
        m["taxen"] += z["taxen"]
        m["zahlungsarten"][z["zahlungsart"]] += z["betrag"]
        if z["vorlaeufig"]:
            m["vorlaeufig"] += z["betrag"]
        for s, b in z["anteile"].items():
            m["je_satz"][s] += b
    total = {"einnahmen": NULL, "taxen": NULL, "je_satz": defaultdict(lambda: NULL), "zahlungsarten": defaultdict(lambda: NULL),
             "vorlaeufig": NULL}
    zeilen = []
    for m in monate:
        saetze = [{"satz": zahl_text(s), "brutto": _r(b), "mwst": _r(mwst_betrag_aus_brutto(b, s))}
                  for s, b in sorted(m["je_satz"].items())]
        zeilen.append({"monat": m["monat"], "name": m["name"], "einnahmen": _r(m["einnahmen"]), "taxen": _r(m["taxen"]),
                       "umsatz_mwst_pflichtig": _r(sum(m["je_satz"].values(), NULL)), "saetze": saetze,
                       "mwst": _r(sum((mwst_betrag_aus_brutto(b, s) for s, b in m["je_satz"].items()), NULL)),
                       "vorlaeufig": _r(m["vorlaeufig"]),
                       "zahlungsarten": {k: _r(v) for k, v in sorted(m["zahlungsarten"].items())}})
        for k in ("einnahmen", "taxen", "vorlaeufig"):
            total[k] += m[k]
        for s, b in m["je_satz"].items():
            total["je_satz"][s] += b
        for k, v in m["zahlungsarten"].items():
            total["zahlungsarten"][k] += v
    return {
        "jahr": jahr, "monate": zeilen,
        "total": {"einnahmen": _r(total["einnahmen"]), "taxen": _r(total["taxen"]),
                  "umsatz_mwst_pflichtig": _r(sum(total["je_satz"].values(), NULL)),
                  "saetze": [{"satz": zahl_text(s), "brutto": _r(b), "mwst": _r(mwst_betrag_aus_brutto(b, s))}
                             for s, b in sorted(total["je_satz"].items())],
                  "mwst": _r(sum((mwst_betrag_aus_brutto(b, s) for s, b in total["je_satz"].items()), NULL)),
                  "vorlaeufig": _r(total["vorlaeufig"]),
                  "zahlungsarten": {k: _r(v) for k, v in sorted(total["zahlungsarten"].items())}},
    }


def uebernachtungen(db: Session, jahr: int) -> dict:
    """Übernachtungen und Taxen je Monat nach der Nacht (Kontrolle zu Feratel)."""
    von, bis = date(jahr, 1, 1), date(jahr + 1, 1, 1)
    saetze = list(db.execute(select(Taxensatz)).scalars())
    leer = lambda: {"erwachsene": 0, "erwachsene_kurtaxe": 0, "kinder": 0, "kleinkinder": 0, "ankuenfte": 0,  # noqa: E731
                    "kurtaxe": NULL, "beherbergungsabgabe": NULL, "plaetze": defaultdict(int)}
    monate = {m: leer() for m in range(1, 13)}
    buchungen = db.execute(select(Buchung).where(Buchung.status.in_(("eingecheckt", "ausgecheckt")),
                                                 Buchung.von < bis, Buchung.bis > von)).scalars()
    for b in buchungen:
        if von <= b.von < bis:
            monate[b.von.month]["ankuenfte"] += 1
        zeilen = b.leistungen or lst.grundzeilen(b)
        for z in zeilen:
            if lst.ist_stueck(z.art):
                continue
            tag = max(z.von, von)
            while tag < min(z.bis, bis):
                m = monate[tag.month]
                if z.art == "erwachsene":
                    m["erwachsene"] += z.anzahl
                    for typ, feld in (("kurtaxe_gemeinde", "kurtaxe"), ("beherbergungsabgabe_kanton", "beherbergungsabgabe")):
                        if typ == "kurtaxe_gemeinde" and not z.kurtaxepflichtig:
                            continue
                        s = _satz_fuer(saetze, typ, tag, 30)
                        if s is not None:
                            m[feld] += Decimal(str(s.betrag_pro_nacht)) * z.anzahl
                    if z.kurtaxepflichtig:
                        m["erwachsene_kurtaxe"] += z.anzahl
                elif z.art in ("kinder", "kleinkinder"):
                    m[z.art] += z.anzahl
                elif z.art in lst.ART and lst.ART[z.art].gruppe in ("stellplatz", "unterkunft"):
                    m["plaetze"][z.art] += z.anzahl
                tag += timedelta(days=1)
    zeilen, total = [], leer()
    for nr, m in monate.items():
        zeile = {"monat": nr, "name": MONATE[nr - 1], **{k: m[k] for k in ("erwachsene", "erwachsene_kurtaxe", "kinder", "kleinkinder", "ankuenfte")},
                 "personennaechte": m["erwachsene"] + m["kinder"] + m["kleinkinder"],
                 "kurtaxe": _r(m["kurtaxe"]), "beherbergungsabgabe": _r(m["beherbergungsabgabe"]),
                 "taxen": _r(m["kurtaxe"] + m["beherbergungsabgabe"]), "plaetze": dict(m["plaetze"])}
        zeilen.append(zeile)
        for k in ("erwachsene", "erwachsene_kurtaxe", "kinder", "kleinkinder", "ankuenfte", "kurtaxe", "beherbergungsabgabe"):
            total[k] += m[k]
        for k, v in m["plaetze"].items():
            total["plaetze"][k] += v
    return {"jahr": jahr, "monate": zeilen, "total": {
        **{k: total[k] for k in ("erwachsene", "erwachsene_kurtaxe", "kinder", "kleinkinder", "ankuenfte")},
        "personennaechte": total["erwachsene"] + total["kinder"] + total["kleinkinder"],
        "kurtaxe": _r(total["kurtaxe"]), "beherbergungsabgabe": _r(total["beherbergungsabgabe"]),
        "taxen": _r(total["kurtaxe"] + total["beherbergungsabgabe"]), "plaetze": dict(total["plaetze"])}}


def saison(db: Session, jahr: int) -> dict:
    """Zusammenstellung des Jahres für die Buchhaltung."""
    rechnungen = list(db.execute(select(Rechnung).where(Rechnung.datum >= date(jahr, 1, 1), Rechnung.datum <= date(jahr, 12, 31))
                                 .order_by(Rechnung.nummer)).scalars())
    gueltig = [r for r in rechnungen if r.status != "storniert"]
    leistungen: dict[str, dict] = {}
    je_satz: dict[Decimal, Decimal] = defaultdict(lambda: NULL)
    taxen: dict[str, Decimal] = defaultdict(lambda: NULL)
    for r in gueltig:
        for p in r.positionen:
            satz, betrag = Decimal(str(p.mwstsatz_prozent)), Decimal(str(p.betrag))
            if satz:
                je_satz[satz] += betrag
                e = leistungen.setdefault(p.artikel.bezeichnung, {"menge": Decimal("0"), "betrag": NULL, "satz": satz})
                e["menge"] += Decimal(str(p.menge))
                e["betrag"] += betrag
            else:
                taxen[p.artikel.bezeichnung] += betrag
    total = sum((Decimal(str(r.gesamtbetrag)) for r in gueltig), NULL)
    anzahlungen = sum((Decimal(str(r.anzahlung or 0)) for r in gueltig), NULL)
    ein = einnahmen(db, jahr)
    ohne_rechnung = [z for z in zahlungen_im_jahr(db, jahr) if z["vorlaeufig"]]
    return {
        "jahr": jahr,
        "rechnungen": {"anzahl": len(gueltig), "storniert": len(rechnungen) - len(gueltig), "total": _r(total),
                       "anzahlungen": _r(anzahlungen), "von": gueltig[0].nummer if gueltig else None,
                       "bis": gueltig[-1].nummer if gueltig else None},
        "leistungen": [{"bezeichnung": k, "menge": zahl_text(v["menge"]), "betrag": _r(v["betrag"]), "satz": zahl_text(v["satz"])}
                       for k, v in sorted(leistungen.items(), key=lambda x: -x[1]["betrag"])],
        "mwst_auf_rechnungen": [{"satz": zahl_text(s), "brutto": _r(b), "mwst": _r(mwst_betrag_aus_brutto(b, s)),
                                 "netto": _r(b - mwst_betrag_aus_brutto(b, s))} for s, b in sorted(je_satz.items())],
        "taxen": [{"bezeichnung": k, "betrag": _r(v)} for k, v in sorted(taxen.items())],
        "taxen_total": _r(sum(taxen.values(), NULL)),
        "einnahmen": ein["total"],
        "offene_rechnungen": [{"nummer": r.nummer, "datum": r.datum, "gast": f"{r.kunde.vorname} {r.kunde.nachname}",
                               "restbetrag": _r(r.restbetrag)} for r in gueltig if r.status == "offen"],
        "anzahlungen_ohne_rechnung": [{"datum": z["datum"], "gast": z["gast"], "reservation": z["referenz"], "betrag": _r(z["betrag"]),
                                       "zahlungsart": z["zahlungsart"]} for z in ohne_rechnung],
    }


def jahre(db: Session) -> list[int]:
    werte = set()
    for (d,) in db.execute(select(Rechnung.datum)):
        werte.add(d.year)
    for (d,) in db.execute(select(Zahlung.eingegangen_am).where(Zahlung.status == "eingegangen")):
        if d:
            werte.add(d.year)
    for (d,) in db.execute(select(Buchung.von).where(Buchung.status.in_(("eingecheckt", "ausgecheckt")))):
        werte.add(d.year)
    werte.add(date.today().year)
    return sorted(werte)
