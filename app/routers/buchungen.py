"""
Buchungen und Aufenthalte (Konzeptdokument Abschnitte 3, 10.6).

Enthält auch die im Konzept geforderte Übersicht "Reservationen je
Monat/Woche/Zeitraum" (Abschnitt 10.6) als einfache Von/Bis-Filterung –
die feste Dropdown-Logik (Monat/Woche vorausberechnen) ist Aufgabe des
Frontends, das Backend liefert bewusst nur eine generische Zeitraum-Query.
"""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.buchung import Aufenthalt, Buchung
from app.schemas.buchung import AufenthaltCreate, AufenthaltOut, BuchungCreate, BuchungOut

router = APIRouter(prefix="/buchungen", tags=["Buchungen"])


@router.post("", response_model=BuchungOut, status_code=201)
def buchung_anlegen(daten: BuchungCreate, db: Session = Depends(get_db)):
    if daten.bis <= daten.von:
        raise HTTPException(400, "'bis' muss nach 'von' liegen")
    buchung = Buchung(**daten.model_dump(), status="bestaetigt")
    db.add(buchung)
    db.commit()
    db.refresh(buchung)
    return buchung


@router.get("", response_model=list[BuchungOut])
def buchungen_auflisten(
    von: date | None = None,
    bis: date | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    """
    Übersicht der Buchungen für einen Zeitraum (Konzept Abschnitt 10.6).
    Frontend übergibt je nach gewählter Dropdown-Option (Monat/Woche/frei)
    die entsprechenden von/bis-Daten.
    """
    stmt = select(Buchung)
    if von:
        stmt = stmt.where(Buchung.bis >= von)
    if bis:
        stmt = stmt.where(Buchung.von <= bis)
    if status:
        stmt = stmt.where(Buchung.status == status)
    stmt = stmt.order_by(Buchung.von)
    return db.execute(stmt).scalars().all()


@router.get("/{buchung_id}", response_model=BuchungOut)
def buchung_lesen(buchung_id: uuid.UUID, db: Session = Depends(get_db)):
    buchung = db.get(Buchung, buchung_id)
    if not buchung:
        raise HTTPException(404, "Buchung nicht gefunden")
    return buchung


@router.post("/{buchung_id}/checkin", response_model=BuchungOut)
def checkin(buchung_id: uuid.UUID, db: Session = Depends(get_db)):
    buchung = db.get(Buchung, buchung_id)
    if not buchung:
        raise HTTPException(404, "Buchung nicht gefunden")
    if buchung.status != "bestaetigt":
        raise HTTPException(400, f"Check-in nicht möglich im Status '{buchung.status}'")
    buchung.status = "eingecheckt"
    db.commit()
    db.refresh(buchung)
    return buchung


@router.post("/{buchung_id}/checkout", response_model=BuchungOut)
def checkout(buchung_id: uuid.UUID, db: Session = Depends(get_db)):
    buchung = db.get(Buchung, buchung_id)
    if not buchung:
        raise HTTPException(404, "Buchung nicht gefunden")
    if buchung.status != "eingecheckt":
        raise HTTPException(400, f"Check-out nicht möglich im Status '{buchung.status}'")
    buchung.status = "ausgecheckt"
    db.commit()
    db.refresh(buchung)
    return buchung


@router.post("/{buchung_id}/aufenthalte", response_model=AufenthaltOut, status_code=201)
def aufenthalt_hinzufuegen(buchung_id: uuid.UUID, daten: AufenthaltCreate, db: Session = Depends(get_db)):
    buchung = db.get(Buchung, buchung_id)
    if not buchung:
        raise HTTPException(404, "Buchung nicht gefunden")
    if daten.buchung_id != buchung_id:
        raise HTTPException(400, "buchung_id im Pfad und im Body stimmen nicht überein")
    if daten.abreise <= daten.ankunft:
        raise HTTPException(400, "'abreise' muss nach 'ankunft' liegen")

    aufenthalt = Aufenthalt(**daten.model_dump())
    db.add(aufenthalt)
    db.commit()
    db.refresh(aufenthalt)
    return aufenthalt


@router.get("/{buchung_id}/aufenthalte", response_model=list[AufenthaltOut])
def aufenthalte_der_buchung(buchung_id: uuid.UUID, db: Session = Depends(get_db)):
    stmt = select(Aufenthalt).where(Aufenthalt.buchung_id == buchung_id)
    return db.execute(stmt).scalars().all()
