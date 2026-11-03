"""Tool-Postfach: Stand des Mailabrufs und nicht zugeordnete Mails."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.models.kommunikation import MailNachricht
from app.models.reservation import Reservationsanfrage
from app.services.anfrage_pruefung import PRUEF_STATUS
from app.services.mail_import import imap_konfiguriert
from app.services.mailverlauf import eigene_adressen, letzter_abruf

router = APIRouter(prefix="/einstellungen/postfach", tags=["Mail-Import"])


class OffeneMail(BaseModel):
    id: uuid.UUID
    richtung: str
    datum: datetime
    von: str
    an: str | None
    betreff: str
    text: str


class PostfachStatus(BaseModel):
    eingerichtet: bool
    server: str | None
    ordner: str
    intervall_sekunden: int
    eigene_adressen: list[str]
    letzter_abruf: str | None
    ergebnis: dict | None
    nicht_zugeordnet: list[OffeneMail]


class Zuordnung(BaseModel):
    anfrage_id: uuid.UUID


@router.get("", response_model=PostfachStatus)
def postfach_status(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    zeit, ergebnis = letzter_abruf(db)
    offen = db.execute(
        select(MailNachricht).where(MailNachricht.reservationsanfrage_id.is_(None)).order_by(MailNachricht.datum.desc())
    ).scalars().all()
    return PostfachStatus(
        eingerichtet=imap_konfiguriert(settings),
        server=f"{settings.imap_host}:{settings.imap_port}" if settings.imap_host else None,
        ordner=settings.imap_ordner,
        intervall_sekunden=settings.mail_import_intervall_sekunden,
        eigene_adressen=sorted(eigene_adressen(settings)),
        letzter_abruf=zeit,
        ergebnis=ergebnis,
        nicht_zugeordnet=[OffeneMail(id=n.id, richtung=n.richtung, datum=n.datum if n.datum.tzinfo else n.datum.replace(tzinfo=timezone.utc),
                                     von=n.von, an=n.an, betreff=n.betreff, text=n.text[:2000]) for n in offen],
    )


@router.post("/mails/{mail_id}/zuordnen", response_model=PostfachStatus)
def mail_zuordnen(mail_id: uuid.UUID, daten: Zuordnung, db: Session = Depends(get_db),
                  settings: Settings = Depends(get_settings)):
    """Ordnet eine nicht zugeordnete Mail von Hand einer Anfrage zu."""
    nachricht = db.get(MailNachricht, mail_id)
    anfrage = db.get(Reservationsanfrage, daten.anfrage_id)
    if not nachricht or not anfrage:
        raise HTTPException(404, "Mail oder Anfrage nicht gefunden")
    nachricht.reservationsanfrage_id = anfrage.id
    if nachricht.richtung == "ausgang" and anfrage.vollstaendig and anfrage.status in PRUEF_STATUS:
        anfrage.status = "erstantwort_gesendet"
    db.commit()
    return postfach_status(db, settings)
