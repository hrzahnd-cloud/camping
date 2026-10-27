"""Einstellungen der Bedienoberfläche: Module ein-/ausschalten."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.module import MODULE_NACH_CODE, modul_setzen, modulstatus

router = APIRouter(prefix="/einstellungen", tags=["Einstellungen"])


class ModulOut(BaseModel):
    code: str
    bezeichnung: str
    beschreibung: str
    aktiv: bool
    umschaltbar: bool


class ModulSchalter(BaseModel):
    aktiv: bool


@router.get("/module", response_model=list[ModulOut])
def module_auflisten(db: Session = Depends(get_db)):
    return modulstatus(db)


@router.put("/module/{code}", response_model=list[ModulOut])
def modul_schalten(code: str, daten: ModulSchalter, db: Session = Depends(get_db)):
    """Schaltet ein Modul im Menü ein oder aus. Daten und API bleiben unverändert."""
    modul = MODULE_NACH_CODE.get(code)
    if modul is None:
        raise HTTPException(404, "Unbekanntes Modul")
    if not modul.umschaltbar:
        raise HTTPException(400, f"Das Modul '{modul.bezeichnung}' ist immer eingeschaltet")
    modul_setzen(db, code, daten.aktiv)
    return modulstatus(db)
