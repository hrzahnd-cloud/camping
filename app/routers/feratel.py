"""
Feratel-Gästemeldung (Konzept Abschnitt 5): Meldeschein-Vorbereitung für den
manuellen Weg über den feratel WebClient und Protokoll der erfassten Meldescheine.
Die maschinelle SOAP-Übertragung ist noch nicht freigeschaltet (siehe
app/services/feratel_client.py).
"""
import uuid
from dataclasses import asdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.buchung import Buchung
from app.models.meldungen import FeratelMeldung
from app.services.feratel_meldeschein import baue_meldeschein

router = APIRouter(prefix="/feratel", tags=["Feratel"])


class MeldescheinErfasst(BaseModel):
    meldescheinnummer: str = Field(min_length=1, max_length=50)


def _buchung(db: Session, buchung_id: uuid.UUID) -> Buchung:
    buchung = db.get(Buchung, buchung_id)
    if not buchung:
        raise HTTPException(404, "Buchung nicht gefunden")
    return buchung


@router.get("/meldeschein/{buchung_id}")
def meldeschein_vorbereiten(buchung_id: uuid.UUID, db: Session = Depends(get_db)):
    """Angaben für den WebClient inkl. fehlender Pflichtangaben und Hinweise."""
    schein = baue_meldeschein(_buchung(db, buchung_id))
    daten = asdict(schein)
    daten["anzahl_personen"] = schein.anzahl_personen
    daten["vollstaendig"] = not schein.fehlende_angaben
    return daten


@router.post("/meldeschein/{buchung_id}/erfasst", status_code=201)
def meldeschein_als_erfasst_speichern(
    buchung_id: uuid.UUID, daten: MeldescheinErfasst, db: Session = Depends(get_db)
):
    """Hält fest, dass der Meldeschein im WebClient erfasst wurde (Nummer für spätere Stornos)."""
    buchung = _buchung(db, buchung_id)
    bestehend = db.execute(
        select(FeratelMeldung).where(FeratelMeldung.aufenthalt_id.in_([a.id for a in buchung.aufenthalte]))
    ).scalars().first()
    if bestehend:
        raise HTTPException(409, f"Für diese Buchung ist bereits ein Meldeschein erfasst ({bestehend.meldescheinnummer})")
    if not buchung.aufenthalte:
        raise HTTPException(409, "Buchung hat keine Aufenthalte")

    jetzt = datetime.now(timezone.utc)
    for aufenthalt in buchung.aufenthalte:
        db.add(FeratelMeldung(
            aufenthalt_id=aufenthalt.id, gesendet_am=jetzt,
            status="manuell_erfasst", meldescheinnummer=daten.meldescheinnummer,
        ))
    db.commit()
    return {"buchung_id": str(buchung.id), "meldescheinnummer": daten.meldescheinnummer,
            "aufenthalte": len(buchung.aufenthalte)}
