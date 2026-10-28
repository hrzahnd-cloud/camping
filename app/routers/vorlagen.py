"""Vorlagenbibliothek für Antwortmails (Konzept Abschnitt 10.3) und Betriebsangaben."""
import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.kommunikation import EmailVorlage
from app.services import antwortmail as am

router = APIRouter(tags=["Antwortmails"])


class VorlageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    typ: str
    sprache: str
    betreff: str
    koerper: str
    aktiv: bool


class VorlageAenderung(BaseModel):
    betreff: str = Field(min_length=1, max_length=300)
    koerper: str = Field(min_length=1, max_length=20000)
    aktiv: bool = True


class VorschauAnfrage(BaseModel):
    betreff: str
    koerper: str
    sprache: str = "de"


class Vorschau(BaseModel):
    betreff: str
    text: str
    unbekannte_platzhalter: list[str]
    warnungen: list[str]


class BetriebFeldOut(BaseModel):
    schluessel: str
    bezeichnung: str
    hinweis: str
    mehrzeilig: bool
    wert: str


@router.get("/email-vorlagen", response_model=list[VorlageOut])
def vorlagen_auflisten(typ: str = am.TYP_ERSTANTWORT, db: Session = Depends(get_db)):
    am.startvorlagen_ergaenzen(db)
    reihenfolge = {s: i for i, s in enumerate(am.SPRACHEN)}
    vorlagen = db.execute(select(EmailVorlage).where(EmailVorlage.typ == typ)).scalars().all()
    return sorted(vorlagen, key=lambda v: reihenfolge.get(v.sprache, 99))


@router.get("/email-vorlagen/platzhalter")
def platzhalter_auflisten() -> list[dict]:
    return [{"name": n, "beschreibung": b} for n, b in am.PLATZHALTER.items()]


@router.put("/email-vorlagen/{vorlage_id}", response_model=VorlageOut)
def vorlage_speichern(vorlage_id: uuid.UUID, daten: VorlageAenderung, db: Session = Depends(get_db)):
    vorlage = db.get(EmailVorlage, vorlage_id)
    if not vorlage:
        raise HTTPException(404, "Vorlage nicht gefunden")
    _, unbekannt = am.ersetze(daten.betreff + "\n" + daten.koerper, {k: "" for k in am.PLATZHALTER})
    if unbekannt:
        raise HTTPException(400, "Unbekannte Platzhalter: " + ", ".join("{{" + u + "}}" for u in unbekannt))
    vorlage.betreff, vorlage.koerper, vorlage.aktiv = daten.betreff, daten.koerper, daten.aktiv
    db.commit()
    db.refresh(vorlage)
    return vorlage


@router.post("/email-vorlagen/vorschau", response_model=Vorschau)
def vorlage_vorschau(daten: VorschauAnfrage, db: Session = Depends(get_db)):
    """Vorschau mit einer erfundenen Anfrage und den aktuellen Betriebsangaben."""
    betrieb = am.betriebsangaben(db)
    werte = am.werte_fuer(am.beispiel_anfrage(), daten.sprache, Decimal("120.00"), date(2027, 3, 31), betrieb)
    betreff, u1 = am.ersetze(daten.betreff, werte)
    text, u2 = am.ersetze(daten.koerper, werte)
    return Vorschau(betreff=betreff, text=text, unbekannte_platzhalter=sorted(set(u1 + u2)),
                    warnungen=am.warnungen_betrieb(betrieb))


@router.get("/einstellungen/betrieb", response_model=list[BetriebFeldOut])
def betrieb_lesen(db: Session = Depends(get_db)):
    werte = am.betriebsangaben(db)
    return [BetriebFeldOut(schluessel=f.schluessel, bezeichnung=f.bezeichnung, hinweis=f.hinweis,
                           mehrzeilig=f.mehrzeilig, wert=werte[f.schluessel]) for f in am.BETRIEBSFELDER]


@router.put("/einstellungen/betrieb", response_model=list[BetriebFeldOut])
def betrieb_speichern(werte: dict[str, str], db: Session = Depends(get_db)):
    unbekannt = set(werte) - am.BETRIEBSSCHLUESSEL
    if unbekannt:
        raise HTTPException(400, "Unbekannte Felder: " + ", ".join(sorted(unbekannt)))
    am.betriebsangaben_setzen(db, werte)
    return betrieb_lesen(db)
