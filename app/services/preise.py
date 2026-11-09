"""
Saisons und Preise (Modul «Artikel & Preise»).

Saisons gelten je Jahr (mit dem Betrieb festgelegt, November 2026):
Vorsaison 1.5.–30.6., Hauptsaison 1.7.–31.8., Nachsaison 1.9.–30.9.; von
Oktober bis April ist der Platz geschlossen. Die Daten lassen sich je Jahr
anpassen, ein neues Jahr übernimmt Saisons und Preise des Vorjahres.

Saisonale Artikel (Personen, Stellplätze, Auto, Motorrad) haben je Saison
einen Preis, ganzjährige (Strom, Umweltabgabe, Wassertank, Zwärgli, Spycher,
Kleinkinder) einen einzigen. Gerechnet wird je Nacht mit dem Preis der Saison
dieser Nacht. Preise sind Endpreise inkl. MWST.

Sonderregeln (camping-aeschi.ch/preise-2):
- Wassertankfüllung CHF 5.– nur bei 1 Übernachtung, ab 2 Nächten inbegriffen.
- Zwärgli/Spycher: Preis pro Nacht für 2 Personen; die ersten 2 Personen je
  Nacht sind inbegriffen, weitere zahlen den Personenpreis (Annahme, mit dem
  Betrieb zu bestätigen). Taxen fallen trotzdem an.
"""
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.artikel import Artikel, ArtikelPreis, Saison
from app.models.buchung import Buchung

SAISON_DATEN = {"vorsaison": ((5, 1), (6, 30)), "hauptsaison": ((7, 1), (8, 31)), "nachsaison": ((9, 1), (9, 30))}
SAISON_NAMEN = {"vorsaison": "Vorsaison", "hauptsaison": "Hauptsaison", "nachsaison": "Nachsaison"}
UNTERKUNFT_PERSONEN_INKL = 2
NULL = Decimal("0.00")


def saisons_im_jahr(db: Session, jahr: int) -> list[Saison]:
    return sorted(db.execute(select(Saison).where(Saison.gueltig_ab >= date(jahr, 1, 1),
                                                  Saison.gueltig_ab <= date(jahr, 12, 31))).scalars(),
                  key=lambda s: s.gueltig_ab)


def jahre(db: Session) -> list[int]:
    return sorted({s.gueltig_ab.year for s in db.execute(select(Saison)).scalars()})


def ist_saisonal(artikel: Artikel) -> bool:
    return any(p.saison_id is not None for p in artikel.preise)


# --- Preise je Nacht -----------------------------------------------------------

class Preiskontext:
    """Lädt Saisons, Artikel und Preise einmal und beantwortet «Preis am Tag»."""

    def __init__(self, db: Session):
        self.db = db
        self.saisons = list(db.execute(select(Saison)).scalars())
        self.artikel = {a.code: a for a in db.execute(select(Artikel)).scalars()}
        self.preise: dict[tuple, Decimal] = {}
        for p in db.execute(select(ArtikelPreis)).scalars():
            self.preise[(p.artikel_id, p.saison_id)] = Decimal(str(p.preis))
        self._mwst: dict[tuple, Decimal] = {}

    def saison_am(self, tag: date) -> Saison | None:
        for s in self.saisons:
            if s.gueltig_ab <= tag <= s.gueltig_bis:
                return s
        return None

    def preis(self, code: str, tag: date) -> Decimal | None:
        a = self.artikel.get(code)
        if a is None:
            return None
        saison = self.saison_am(tag)
        if saison is not None and (a.id, saison.id) in self.preise:
            return self.preise[(a.id, saison.id)]
        if any(k[0] == a.id and k[1] is not None for k in self.preise):
            return None  # saisonaler Artikel ausserhalb der Saison: geschlossen
        return self.preise.get((a.id, None))

    def ist_saisonal(self, code: str) -> bool:
        a = self.artikel.get(code)
        return a is not None and any(k[0] == a.id and k[1] is not None for k in self.preise)

    def mwst(self, code: str, tag: date) -> Decimal | None:
        from app.services.mwst import prozent_fuer_artikel
        a = self.artikel.get(code)
        if a is None:
            return None
        schluessel = (code, tag)
        if schluessel not in self._mwst:
            try:
                self._mwst[schluessel] = Decimal(str(prozent_fuer_artikel(self.db, a, tag)))
            except ValueError:
                self._mwst[schluessel] = None
        return self._mwst[schluessel]


@dataclass
class ZeilenPreis:
    leistung_id: uuid.UUID | None
    bezeichnung: str
    betrag: Decimal = NULL
    einzelpreise: list[Decimal] = field(default_factory=list)
    """Unterschiedliche Preise im Zeitraum (z.B. Vor- und Hauptsaison)."""
    naechte_ohne_preis: int = 0
    mwst_prozent: Decimal | None = None
    hinweis: str | None = None
    teile: list[list] = field(default_factory=list)
    """[[saison_typ|None, einzelpreis, menge], …] – für Rechnungszeilen je Saison und Preis."""
    artikel_code: str | None = None

    @property
    def einzelpreis(self) -> Decimal | None:
        return self.einzelpreise[0] if len(self.einzelpreise) == 1 else None


@dataclass
class Preisrechnung:
    zeilen: list[ZeilenPreis]
    abzuege: list[ZeilenPreis]
    total: Decimal
    mwst_total: Decimal
    fehlende_preise: bool


def _mwst_anteil(betrag: Decimal, prozent: Decimal | None) -> Decimal:
    if not prozent:
        return NULL
    return (betrag - betrag / (1 + prozent / 100)).quantize(Decimal("0.01"))


def berechne(db: Session, b: Buchung, art_code) -> Preisrechnung:
    """
    Preise der Leistungen eines Aufenthalts. `art_code(art)` liefert den
    Artikelcode einer Leistungsart (siehe app/services/leistungen.py).
    """
    from app.services import leistungen as lst

    ctx = Preiskontext(db)
    naechte_total = (b.bis - b.von).days
    zeilen, mwst_total = [], NULL
    for z in sorted(b.leistungen, key=lambda z: (z.von, z.art)):
        code = art_code(z.art)
        zp = ZeilenPreis(leistung_id=z.id, bezeichnung=lst.ART[z.art].bezeichnung if z.art in lst.ART else z.art,
                         artikel_code=code)
        tage = [z.von] if lst.ist_stueck(z.art) else [z.von + timedelta(days=i) for i in range(z.naechte)]
        for tag in tage:
            p = ctx.preis(code, tag)
            if z.art == "wassertank" and naechte_total >= 2:
                p, zp.hinweis = NULL, "ab 2 Nächten inbegriffen"
            if p is None:
                zp.naechte_ohne_preis += 1
                continue
            if p not in zp.einzelpreise:
                zp.einzelpreise.append(p)
            saison = ctx.saison_am(tag)
            styp = saison.typ if saison and ctx.ist_saisonal(code) else None
            if zp.teile and zp.teile[-1][0] == styp and zp.teile[-1][1] == p:
                zp.teile[-1][2] += z.anzahl
            else:
                zp.teile.append([styp, p, z.anzahl])
            anteil = p * z.anzahl
            zp.betrag += anteil
            prozent = ctx.mwst(code, tag)
            zp.mwst_prozent = prozent
            mwst_total += _mwst_anteil(anteil, prozent)
        if zp.naechte_ohne_preis and not zp.hinweis:
            zp.hinweis = ("kein Preis hinterlegt" if zp.naechte_ohne_preis == len(tage)
                          else f"{zp.naechte_ohne_preis} von {len(tage)} Nächten ohne Preis (ausserhalb der Saison)")
        zeilen.append(zp)

    # Zwärgli/Spycher: 2 Personen je Nacht inbegriffen
    abzuege = []
    if b.stellplatz_typ in ("zwaergli", "spycher"):
        name = lst.ART[b.stellplatz_typ].bezeichnung
        ab = ZeilenPreis(leistung_id=None, bezeichnung=f"Inbegriffen im {name} ({UNTERKUNFT_PERSONEN_INKL} Personen je Nacht)",
                         artikel_code=art_code("erwachsene"))
        for tag, (e, k, _kk) in lst.personen_je_nacht(b).items():
            frei = UNTERKUNFT_PERSONEN_INKL
            for art, anzahl in (("erwachsene", e), ("kinder", k)):
                n = min(frei, anzahl)
                frei -= n
                p = ctx.preis(art_code(art), tag)
                if n and p:
                    ab.betrag -= p * n
                    ab.mwst_prozent = ctx.mwst(art_code(art), tag)
                    mwst_total -= _mwst_anteil(p * n, ab.mwst_prozent)
        if ab.betrag:
            abzuege.append(ab)

    total = sum((z.betrag for z in zeilen + abzuege), NULL)
    return Preisrechnung(zeilen=zeilen, abzuege=abzuege, total=total.quantize(Decimal("0.01")),
                         mwst_total=mwst_total.quantize(Decimal("0.01")),
                         fehlende_preise=any(z.naechte_ohne_preis for z in zeilen))


# --- Pflege je Jahr -------------------------------------------------------------

def jahr_uebernehmen(db: Session, jahr: int, von_jahr: int) -> list[Saison]:
    """Saisons und Preise von `von_jahr` ins Jahr `jahr` kopieren (gleiche Tage)."""
    if saisons_im_jahr(db, jahr):
        raise ValueError(f"Für {jahr} sind bereits Saisons erfasst")
    quelle = saisons_im_jahr(db, von_jahr)
    if not quelle:
        raise ValueError(f"Für {von_jahr} sind keine Saisons erfasst")
    neue = []
    for s in quelle:
        try:
            ab, bis = s.gueltig_ab.replace(year=jahr), s.gueltig_bis.replace(year=jahr)
        except ValueError:  # 29. Februar
            ab, bis = s.gueltig_ab.replace(year=jahr, day=28), s.gueltig_bis.replace(year=jahr, day=28)
        name = f"{SAISON_NAMEN[s.typ]} {jahr}" if s.typ in SAISON_NAMEN else s.bezeichnung.replace(str(von_jahr), str(jahr))
        n = Saison(typ=s.typ, bezeichnung=name, gueltig_ab=ab, gueltig_bis=bis)
        db.add(n)
        db.flush()
        for p in s.artikelpreise:
            db.add(ArtikelPreis(artikel_id=p.artikel_id, saison_id=n.id, preis=p.preis))
        neue.append(n)
    db.commit()
    return neue
