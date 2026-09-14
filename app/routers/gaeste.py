"""Gäste-Verwaltung (Stammdaten, siehe Konzeptdokument Abschnitt 3)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.buchung import Gast
from app.schemas.buchung import GastCreate, GastOut

router = APIRouter(prefix="/gaeste", tags=["Gäste"])


@router.post("", response_model=GastOut, status_code=201)
def gast_anlegen(daten: GastCreate, db: Session = Depends(get_db)):
    gast = Gast(**daten.model_dump())
    db.add(gast)
    db.commit()
    db.refresh(gast)
    return gast


@router.get("", response_model=list[GastOut])
def gaeste_auflisten(suche: str | None = None, db: Session = Depends(get_db)):
    stmt = select(Gast)
    if suche:
        stmt = stmt.where(Gast.nachname.ilike(f"%{suche}%"))
    stmt = stmt.order_by(Gast.nachname)
    return db.execute(stmt).scalars().all()


@router.get("/{gast_id}", response_model=GastOut)
def gast_lesen(gast_id: uuid.UUID, db: Session = Depends(get_db)):
    gast = db.get(Gast, gast_id)
    if not gast:
        raise HTTPException(404, "Gast nicht gefunden")
    return gast


@router.put("/{gast_id}", response_model=GastOut)
def gast_aktualisieren(gast_id: uuid.UUID, daten: GastCreate, db: Session = Depends(get_db)):
    gast = db.get(Gast, gast_id)
    if not gast:
        raise HTTPException(404, "Gast nicht gefunden")
    for feld, wert in daten.model_dump().items():
        setattr(gast, feld, wert)
    db.commit()
    db.refresh(gast)
    return gast
