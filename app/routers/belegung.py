"""
Belegungsübersicht nach Stellplatz-Typ (Konzept Abschnitt 10.6).

Die Zuteilung einzelner Stellplätze erfolgt ausserhalb des Tools. Die
Übersicht zeigt deshalb je Stellplatz-Typ (Zelt, Wohnwagen, Camper,
Zwärgli, Spycher), welche Reservationen in einem Zeitraum anstehen –
mit Anzahl Erwachsene (E) und Kinder (K).

Gezählt wird pro Nacht: Anreisetag zählt, Abreisetag nicht.
"""
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.reservation import Reservationsanfrage

router = APIRouter(prefix="/belegung", tags=["Belegung"])

TYPEN = ("zeltwiese", "wohnwagen", "camper", "zwaergli", "spycher")
AKZEPTIERT = {"bezahlt_akzeptiert"}
OFFEN = {"neu", "unvollstaendig", "geprueft_vollstaendig", "erstantwort_gesendet", "zahlung_ausstehend"}
MAX_TAGE = 400


class BelegungEintrag(BaseModel):
    anfrage_id: str
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


class Belegung(BaseModel):
    von: date
    bis: date
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

    tage = [von + timedelta(days=i) for i in range((bis - von).days + 1)]
    summen = {t: {d: [0, 0, 0] for d in tage} for t in TYPEN}
    anzahl = {t: 0 for t in TYPEN}
    eintraege = []
    for a in anfragen:
        e, k = a.anzahl_erwachsene or 0, a.anzahl_kinder or 0
        eintraege.append(BelegungEintrag(
            anfrage_id=str(a.id), gast_name=a.gast_name, stellplatz_typ=a.stellplatz_typ,
            von=a.gewuenscht_von, bis=a.gewuenscht_bis,
            naechte=(a.gewuenscht_bis - a.gewuenscht_von).days,
            erwachsene=e, kinder=k, status=a.status, akzeptiert=a.status in AKZEPTIERT,
        ))
        if a.stellplatz_typ not in summen:
            continue
        anzahl[a.stellplatz_typ] += 1
        for d in tage:
            if a.gewuenscht_von <= d < a.gewuenscht_bis:
                zeile = summen[a.stellplatz_typ][d]
                zeile[0] += 1
                zeile[1] += e
                zeile[2] += k

    nach_typ = [
        TypUebersicht(
            stellplatz_typ=t,
            anzahl_reservationen=anzahl[t],
            tage=[TagesSumme(datum=d, anzahl=v[0], erwachsene=v[1], kinder=v[2]) for d, v in summen[t].items()],
        )
        for t in TYPEN
    ]
    return Belegung(von=von, bis=bis, eintraege=eintraege, nach_typ=nach_typ)
