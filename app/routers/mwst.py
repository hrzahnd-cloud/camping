"""MWST-Sätze verwalten (Konzept Abschnitt 9.1): je Code historisiert nach Gültigkeit."""
import uuid
from collections import defaultdict
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.artikel import Mwstsatz
from app.services import mwst

router = APIRouter(prefix="/mwst-saetze", tags=["MWST"])

REIHENFOLGE = {"BEHERBERGUNG": 0, "NORMAL": 1, "REDUZIERT": 2, "AUSGENOMMEN": 3}


class SatzOut(BaseModel):
    id: uuid.UUID
    satz_prozent: Decimal
    gueltig_ab: date
    gueltig_bis: date | None
    aktuell: bool
    zukuenftig: bool


class CodeOut(BaseModel):
    code: str
    bezeichnung: str
    aktueller_satz: Decimal | None
    saetze: list[SatzOut]


class NeuerSatz(BaseModel):
    satz_prozent: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)
    gueltig_ab: date


@router.get("", response_model=list[CodeOut])
def saetze_auflisten(db: Session = Depends(get_db)):
    heute = date.today()
    gruppen: dict[str, list[Mwstsatz]] = defaultdict(list)
    for s in db.execute(select(Mwstsatz).order_by(Mwstsatz.gueltig_ab.desc())).scalars():
        gruppen[s.code].append(s)
    ergebnis = []
    for code, saetze in sorted(gruppen.items(), key=lambda kv: (REIHENFOLGE.get(kv[0], 9), kv[0])):
        aktuell = mwst.gueltigen_mwstsatz_ermitteln(saetze, heute)
        ergebnis.append(CodeOut(
            code=code,
            bezeichnung=(aktuell or saetze[0]).bezeichnung,
            aktueller_satz=aktuell.satz_prozent if aktuell else None,
            saetze=[SatzOut(id=s.id, satz_prozent=s.satz_prozent, gueltig_ab=s.gueltig_ab, gueltig_bis=s.gueltig_bis,
                            aktuell=aktuell is not None and s.id == aktuell.id, zukuenftig=s.gueltig_ab > heute)
                    for s in saetze],
        ))
    return ergebnis


@router.post("/{code}", response_model=list[CodeOut], status_code=201)
def satz_hinterlegen(code: str, daten: NeuerSatz, db: Session = Depends(get_db)):
    """Neuer Satz ab Datum, z.B. jährlich per 1. Januar. Der bisherige endet am Vortag."""
    try:
        mwst.neuen_satz_hinterlegen(db, code, daten.satz_prozent, daten.gueltig_ab)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return saetze_auflisten(db)


@router.delete("/{satz_id}", response_model=list[CodeOut])
def satz_entfernen(satz_id: uuid.UUID, db: Session = Depends(get_db)):
    """Korrigiert eine Fehleingabe: nur der jüngste, noch nicht gültige Satz."""
    try:
        mwst.letzten_satz_entfernen(db, satz_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return saetze_auflisten(db)
