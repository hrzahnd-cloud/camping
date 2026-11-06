"""
Belegungsübersicht nach Stellplatz-Typ (Konzept Abschnitt 10.6).

Die Zuteilung einzelner Stellplätze erfolgt ausserhalb des Tools. Die
Übersicht zeigt deshalb je Stellplatz-Typ (Zelt, Wohnwagen, Camper,
Zwärgli, Spycher), welche Reservationen in einem Zeitraum anstehen –
mit Anzahl Erwachsene (E) und Kinder (K).

Gezählt wird pro Nacht: Anreisetag zählt, Abreisetag nicht.

Neben Reservationen erscheinen Aufenthalte (Buchungen, Check-in am
Anreisetag oder ohne Reservation). Die Zeile «Auslastung» zählt nur, was
einen Platz belegt (siehe app/services/belegung.py).
"""
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.reservation import Reservationsanfrage
from app.services import belegung as bel

router = APIRouter(prefix="/belegung", tags=["Belegung"])

TYPEN = ("zeltwiese", "wohnwagen", "camper", "zwaergli", "spycher")
AKZEPTIERT = {"bezahlt_akzeptiert"}
OFFEN = {"neu", "unvollstaendig", "geprueft_vollstaendig", "in_abklaerung", "erstantwort_gesendet", "zahlung_ausstehend"}
MAX_TAGE = 400


class BelegungEintrag(BaseModel):
    art: Literal["reservation", "aufenthalt"] = "reservation"
    id: str
    anfrage_id: str | None = None
    buchung_id: str | None = None
    nummer: str | None = None
    platz: str | None = None
    gast_name: str
    stellplatz_typ: str | None
    von: date
    bis: date
    naechte: int
    erwachsene: int
    kinder: int
    status: str
    akzeptiert: bool


class TagesSumme(BaseModel):
    datum: date
    anzahl: int
    erwachsene: int
    kinder: int


class TypUebersicht(BaseModel):
    stellplatz_typ: str
    anzahl_reservationen: int
    tage: list[TagesSumme]


class Auslastung(BaseModel):
    datum: date
    belegt: int
    """Belegte Stellplätze (Zelt, Wohnwagen, Camper) in dieser Nacht."""
    stufe: Literal["normal", "hoch", "voll"]


class Belegung(BaseModel):
    von: date
    bis: date
    plaetze: int
    meldung_ab: int
    auslastung: list[Auslastung]
    eintraege: list[BelegungEintrag]
    nach_typ: list[TypUebersicht]


@router.get("", response_model=Belegung)
def belegung(
    von: date,
    bis: date,
    status: Literal["alle", "akzeptiert", "offen"] = "alle",
    db: Session = Depends(get_db),
):
    """
    Reservationen, die sich mit dem Zeitraum [von, bis] überschneiden.
    `status`: alle (akzeptierte und offene) | akzeptiert | offen.
    Abgelehnte und stornierte Anfragen sowie Anfragen ohne Zeitraum
    erscheinen nie.
    """
    if bis < von:
        raise HTTPException(400, "'bis' liegt vor 'von'")
    if (bis - von).days > MAX_TAGE:
        raise HTTPException(400, f"Zeitraum zu lang (max. {MAX_TAGE} Tage)")

    erlaubte = {"alle": AKZEPTIERT | OFFEN, "akzeptiert": AKZEPTIERT, "offen": OFFEN}[status]
    stmt = (
        select(Reservationsanfrage)
        .where(Reservationsanfrage.status.in_(erlaubte))
        .where(Reservationsanfrage.gewuenscht_von.is_not(None))
        .where(Reservationsanfrage.gewuenscht_bis.is_not(None))
        .where(Reservationsanfrage.gewuenscht_von <= bis)
        .where(Reservationsanfrage.gewuenscht_bis > von)
        .order_by(Reservationsanfrage.gewuenscht_von, Reservationsanfrage.gast_name)
    )
    anfragen = db.execute(stmt).scalars().all()
    # Aufenthalte belegen immer einen Platz; bei «nur offene» nicht zeigen
    buchungen = [] if status == "offen" else bel.belegende_aufenthalte(db, von, bis)

    tage = [von + timedelta(days=i) for i in range((bis - von).days + 1)]
    summen = {t: {d: [0, 0, 0] for d in tage} for t in TYPEN}
    anzahl = {t: 0 for t in TYPEN}
    eintraege = []

    def zaehlen(typ, start, ende, e, k):
        if typ not in summen:
            return
        anzahl[typ] += 1
        for d in tage:
            if start <= d < ende:
                zeile = summen[typ][d]
                zeile[0] += 1
                zeile[1] += e
                zeile[2] += k

    for a in anfragen:
        e, k = a.anzahl_erwachsene or 0, a.anzahl_kinder or 0
        eintraege.append(BelegungEintrag(
            id=str(a.id), anfrage_id=str(a.id), nummer=a.nummer, gast_name=a.gast_name, stellplatz_typ=a.stellplatz_typ,
            von=a.gewuenscht_von, bis=a.gewuenscht_bis,
            naechte=(a.gewuenscht_bis - a.gewuenscht_von).days,
            erwachsene=e, kinder=k, status=a.status, akzeptiert=a.status in AKZEPTIERT,
        ))
        zaehlen(a.stellplatz_typ, a.gewuenscht_von, a.gewuenscht_bis, e, k)
    for b in buchungen:
        anfrage = db.get(Reservationsanfrage, b.reservationsanfrage_id) if b.reservationsanfrage_id else None
        gast = b.hauptgast
        eintraege.append(BelegungEintrag(
            art="aufenthalt", id=str(b.id), buchung_id=str(b.id),
            anfrage_id=str(anfrage.id) if anfrage else None, nummer=anfrage.nummer if anfrage else None,
            platz=b.platz, gast_name=f"{gast.vorname} {gast.nachname}".strip() if gast else "?",
            stellplatz_typ=b.stellplatz_typ, von=b.von, bis=b.bis, naechte=(b.bis - b.von).days,
            erwachsene=b.anzahl_erwachsene or 0, kinder=b.anzahl_kinder or 0, status=b.status, akzeptiert=True,
        ))
        zaehlen(b.stellplatz_typ, b.von, b.bis, b.anzahl_erwachsene or 0, b.anzahl_kinder or 0)
    eintraege.sort(key=lambda x: (x.von, x.gast_name))

    werte = bel.einstellungen(db)
    plaetze, meldung_ab = werte["belegung_plaetze"], werte["belegung_meldung_ab"]
    auslastung = [
        Auslastung(datum=d, belegt=n, stufe="voll" if n >= plaetze else "hoch" if n >= meldung_ab else "normal")
        for d, n in bel.stellplaetze_je_nacht(db, von, bis).items()
    ]

    nach_typ = [
        TypUebersicht(
            stellplatz_typ=t,
            anzahl_reservationen=anzahl[t],
            tage=[TagesSumme(datum=d, anzahl=v[0], erwachsene=v[1], kinder=v[2]) for d, v in summen[t].items()],
        )
        for t in TYPEN
    ]
    return Belegung(von=von, bis=bis, plaetze=plaetze, meldung_ab=meldung_ab, auslastung=auslastung,
                    eintraege=eintraege, nach_typ=nach_typ)


class BelegungEinstellungen(BaseModel):
    belegung_plaetze: int
    belegung_meldung_ab: int


@router.get("/einstellungen", response_model=BelegungEinstellungen)
def einstellungen_lesen(db: Session = Depends(get_db)):
    return bel.einstellungen(db)


@router.put("/einstellungen", response_model=BelegungEinstellungen)
def einstellungen_speichern(daten: BelegungEinstellungen, db: Session = Depends(get_db)):
    if daten.belegung_plaetze < 1 or not 1 <= daten.belegung_meldung_ab <= daten.belegung_plaetze:
        raise HTTPException(400, "Die Meldegrenze muss zwischen 1 und der Anzahl Plätze liegen")
    return bel.einstellungen_setzen(db, daten.model_dump())


class NichtAngereist(BaseModel):
    anfrage_id: str
    nummer: str | None
    gast_name: str
    gast_telefon: str | None
    stellplatz_typ: str | None
    von: date
    bis: date
    erwachsene: int
    kinder: int


@router.get("/nicht-angereist", response_model=list[NichtAngereist])
def nicht_angereist(stichtag: date | None = None, tage: int = 14, db: Session = Depends(get_db)):
    """
    Akzeptierte Reservationen, deren Anreisetag vor dem Stichtag (Standard:
    heute) liegt und für die weder ein Aufenthalt erfasst noch «nicht
    erschienen» gesetzt ist – die Meldung am Morgen danach.
    """
    stichtag = stichtag or date.today()
    anfragen = db.execute(
        select(Reservationsanfrage).where(
            Reservationsanfrage.status == bel.AKZEPTIERT,
            Reservationsanfrage.gewuenscht_von < stichtag,
            Reservationsanfrage.gewuenscht_von >= stichtag - timedelta(days=tage),
        ).order_by(Reservationsanfrage.gewuenscht_von, Reservationsanfrage.gast_name)
    ).scalars().all()
    return [NichtAngereist(anfrage_id=str(a.id), nummer=a.nummer, gast_name=a.gast_name, gast_telefon=a.gast_telefon,
                           stellplatz_typ=a.stellplatz_typ, von=a.gewuenscht_von, bis=a.gewuenscht_bis,
                           erwachsene=a.anzahl_erwachsene or 0, kinder=a.anzahl_kinder or 0) for a in anfragen]
