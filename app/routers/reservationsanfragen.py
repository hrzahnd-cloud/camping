"""
Reservationsanfragen (Konzeptdokument Abschnitt 10).

Deckt aktuell ab: Anlegen, Auflisten/Filtern, Vollständigkeitsprüfung.
NICHT enthalten (siehe Konzept, bewusst offen): automatischer E-Mail-Import
(Kanal 'email' wird heute von einer Person erfasst), Homepage-Formular-
Anbindung (Abschnitt 10.7 – Entscheidung noch offen), automatischer
Erstantwort-Versand (Versand ist laut Konzept immer durch eine Person
ausgelöst, siehe /email-versenden unten als vorbereiteter Endpunkt).
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.reservation import Reservationsanfrage
from app.schemas.reservation import ReservationsanfrageCreate, ReservationsanfrageOut

router = APIRouter(prefix="/reservationsanfragen", tags=["Reservationsanfragen"])


def _pruefe_vollstaendigkeit(anfrage: Reservationsanfrage) -> tuple[bool, list[str]]:
    """
    Prüft die Pflichtfelder einer Anfrage (Konzept Abschnitt 10.1).
    Gibt (vollstaendig, liste_fehlender_felder) zurück.
    """
    fehlend = []
    if not anfrage.gast_email:
        fehlend.append("gast_email")
    if not anfrage.gewuenscht_von or not anfrage.gewuenscht_bis:
        fehlend.append("zeitraum")
    elif anfrage.gewuenscht_bis <= anfrage.gewuenscht_von:
        fehlend.append("zeitraum_ungueltig")
    if not anfrage.stellplatz_typ:
        fehlend.append("stellplatz_typ")
    if anfrage.anzahl_erwachsene < 1:
        fehlend.append("anzahl_erwachsene")
    return (len(fehlend) == 0, fehlend)


@router.post("", response_model=ReservationsanfrageOut, status_code=201)
def anfrage_anlegen(daten: ReservationsanfrageCreate, db: Session = Depends(get_db)):
    anfrage = Reservationsanfrage(**daten.model_dump())
    vollstaendig, fehlend = _pruefe_vollstaendigkeit(anfrage)
    anfrage.vollstaendig = vollstaendig
    anfrage.fehlende_angaben = ",".join(fehlend) if fehlend else None
    anfrage.status = "geprueft_vollstaendig" if vollstaendig else "unvollstaendig"

    db.add(anfrage)
    db.commit()
    db.refresh(anfrage)
    return anfrage


@router.get("", response_model=list[ReservationsanfrageOut])
def anfragen_auflisten(
    status: str | None = None,
    nur_vollstaendige: bool = False,
    db: Session = Depends(get_db),
):
    stmt = select(Reservationsanfrage)
    if status:
        stmt = stmt.where(Reservationsanfrage.status == status)
    if nur_vollstaendige:
        stmt = stmt.where(Reservationsanfrage.vollstaendig.is_(True))
    stmt = stmt.order_by(Reservationsanfrage.eingangs_datum.desc())
    return db.execute(stmt).scalars().all()


@router.get("/{anfrage_id}", response_model=ReservationsanfrageOut)
def anfrage_lesen(anfrage_id: uuid.UUID, db: Session = Depends(get_db)):
    anfrage = db.get(Reservationsanfrage, anfrage_id)
    if not anfrage:
        raise HTTPException(404, "Reservationsanfrage nicht gefunden")
    return anfrage


@router.post("/{anfrage_id}/zahlung-bestaetigen", response_model=ReservationsanfrageOut)
def zahlung_bestaetigen(anfrage_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Markiert die Anzahlung als eingegangen (Konzept Abschnitt 10.5).

    HINWEIS: Erzeugt hier bewusst NOCH NICHT automatisch die Buchung –
    das sollte im nächsten Ausbauschritt ergänzt werden (Buchung aus
    Reservationsanfrage-Daten ableiten: Stellplatz-Zuordnung, Gast anlegen
    o. verknüpfen, etc. sind fachliche Entscheidungen, die hier bewusst
    nicht "geraten" werden).
    """
    anfrage = db.get(Reservationsanfrage, anfrage_id)
    if not anfrage:
        raise HTTPException(404, "Reservationsanfrage nicht gefunden")
    if not anfrage.vollstaendig:
        raise HTTPException(400, "Anfrage ist nicht vollständig – Zahlung kann nicht bestätigt werden")

    anfrage.status = "bezahlt_akzeptiert"
    db.commit()
    db.refresh(anfrage)
    return anfrage
