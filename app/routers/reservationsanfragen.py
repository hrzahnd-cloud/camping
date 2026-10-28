"""
Reservationsanfragen (Konzeptdokument Abschnitt 10).

Deckt ab: Anlegen, Auflisten/Filtern, Vollständigkeitsprüfung und die
Übernahme von Anfragen aus E-Mails (IMAP-Postfach oder .eml-Datei, siehe
app/services/mail_import.py).
NICHT enthalten (siehe Konzept, bewusst offen): Homepage-Formular-
Anbindung (Abschnitt 10.7 – Entscheidung noch offen), automatischer
Erstantwort-Versand (Versand ist laut Konzept immer durch eine Person
ausgelöst).
"""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.models.kommunikation import EmailVersand, EmailVorlage
from app.models.reservation import Reservationsanfrage
from app.schemas.reservation import (
    ReservationsanfrageCreate,
    ReservationsanfrageDetail,
    ReservationsanfrageOut,
    ReservationsanfrageUpdate,
    StatusAenderung,
)
from app.services import antwortmail as am
from app.services.anfrage_pruefung import wende_pruefung_an
from app.services.mail_import import (
    MailImportNichtKonfiguriert,
    importiere_aus_postfach,
    importiere_mail,
    parse_mailtext,
    speichere_anfrage,
)

router = APIRouter(prefix="/reservationsanfragen", tags=["Reservationsanfragen"])


@router.post("/mail-import", tags=["Mail-Import"])
def mail_import_ausloesen(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    """Holt ungelesene Mails aus dem IMAP-Postfach und legt Anfragen an."""
    try:
        ergebnis = importiere_aus_postfach(db, settings)
    except MailImportNichtKonfiguriert as exc:
        raise HTTPException(503, f"Mail-Import nicht konfiguriert: {exc}")
    except OSError as exc:
        raise HTTPException(502, f"Postfach nicht erreichbar: {exc}")
    return {
        "neu": ergebnis.neu, "duplikate": ergebnis.duplikate,
        "uebersprungen": ergebnis.uebersprungen, "fehler": ergebnis.fehler,
    }


class Mailtext(BaseModel):
    text: str = Field(min_length=10, max_length=20000)


@router.post("/mail-import/text", response_model=ReservationsanfrageDetail, status_code=201, tags=["Mail-Import"])
def mail_aus_text_importieren(daten: Mailtext, db: Session = Depends(get_db)):
    """
    Übernimmt den eingefügten Text einer Reservationsmail (z.B. aus dem
    Homepage-Formular), solange das Postfach noch nicht angebunden ist.
    """
    parsed = parse_mailtext(daten.text)
    if parsed is None:
        raise HTTPException(422, "Im Text steht keine E-Mail-Adresse des Gastes")
    anfrage = speichere_anfrage(db, parsed)
    if anfrage is None:
        raise HTTPException(409, "Dieser Mailtext wurde bereits übernommen")
    return anfrage


@router.post("/mail-import/eml", response_model=ReservationsanfrageOut, status_code=201, tags=["Mail-Import"])
async def mail_aus_eml_importieren(request: Request, db: Session = Depends(get_db)):
    """Übernimmt eine einzelne Mail (Rohformat .eml im Request-Body), z.B. eine weitergeleitete Anfrage."""
    roh = await request.body()
    if not roh:
        raise HTTPException(400, "Leerer Request-Body: erwartet wird der Inhalt einer .eml-Datei")
    anfrage, art = importiere_mail(db, roh)
    if art == "duplikat":
        raise HTTPException(409, "Diese Mail wurde bereits importiert")
    if anfrage is None:
        raise HTTPException(422, "Mail enthält keinen verwertbaren Absender oder ist eine automatische Nachricht")
    return anfrage


@router.post("", response_model=ReservationsanfrageOut, status_code=201)
def anfrage_anlegen(daten: ReservationsanfrageCreate, db: Session = Depends(get_db)):
    anfrage = Reservationsanfrage(**daten.model_dump())
    wende_pruefung_an(anfrage)

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


@router.get("/{anfrage_id}", response_model=ReservationsanfrageDetail)
def anfrage_lesen(anfrage_id: uuid.UUID, db: Session = Depends(get_db)):
    anfrage = db.get(Reservationsanfrage, anfrage_id)
    if not anfrage:
        raise HTTPException(404, "Reservationsanfrage nicht gefunden")
    return anfrage


@router.patch("/{anfrage_id}", response_model=ReservationsanfrageDetail)
def anfrage_aendern(anfrage_id: uuid.UUID, daten: ReservationsanfrageUpdate, db: Session = Depends(get_db)):
    """Angaben ändern bzw. nachtragen; die Vollständigkeit wird neu geprüft."""
    anfrage = db.get(Reservationsanfrage, anfrage_id)
    if not anfrage:
        raise HTTPException(404, "Reservationsanfrage nicht gefunden")
    for feld, wert in daten.model_dump(exclude_unset=True).items():
        setattr(anfrage, feld, wert)
    wende_pruefung_an(anfrage)
    db.commit()
    db.refresh(anfrage)
    return anfrage


# Status, die nur eine vollständige Anfrage erreichen darf
_STATUS_NUR_VOLLSTAENDIG = {"erstantwort_gesendet", "zahlung_ausstehend", "bezahlt_akzeptiert"}


@router.post("/{anfrage_id}/status", response_model=ReservationsanfrageDetail)
def status_setzen(anfrage_id: uuid.UUID, daten: StatusAenderung, db: Session = Depends(get_db)):
    """
    Setzt den Bearbeitungsstatus (Konzept 10.2–10.5), z.B. "Erstantwort
    gesendet" oder "abgelehnt". Die Mail selbst wird (noch) ausserhalb
    verschickt; hier wird nur festgehalten, wo die Anfrage steht.
    """
    anfrage = db.get(Reservationsanfrage, anfrage_id)
    if not anfrage:
        raise HTTPException(404, "Reservationsanfrage nicht gefunden")
    if daten.status in _STATUS_NUR_VOLLSTAENDIG and not anfrage.vollstaendig:
        raise HTTPException(
            400, f"Anfrage ist unvollständig ({anfrage.fehlende_angaben}) – zuerst Angaben ergänzen"
        )
    if daten.status in {"neu", "unvollstaendig", "geprueft_vollstaendig"}:
        # zurück in die Prüfung: Status ergibt sich aus der Vollständigkeit
        anfrage.status = "neu"
        wende_pruefung_an(anfrage)
    else:
        anfrage.status = daten.status
    db.commit()
    db.refresh(anfrage)
    return anfrage


@router.post("/{anfrage_id}/zahlung-bestaetigen", response_model=ReservationsanfrageDetail)
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


# --- Antwort mit Zahlungsinformationen (Konzept 10.2) ------------------------------

class AntwortVorbereiten(BaseModel):
    sprache: str = Field(pattern="^(de|fr|it|en)$")
    betrag: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    zahlungsfrist: date | None = None


class AntwortEntwurf(BaseModel):
    vorlage_id: uuid.UUID
    sprache: str
    empfaenger: str
    betreff: str
    text: str
    warnungen: list[str]


class AntwortGesendet(BaseModel):
    vorlage_id: uuid.UUID
    betreff: str = Field(min_length=1, max_length=300)
    text: str = Field(min_length=1, max_length=50000)


class VersandOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    gesendet_am: datetime
    empfaenger: str
    betreff_final: str
    koerper_final: str
    status: str


def _vollstaendige_anfrage(db: Session, anfrage_id: uuid.UUID) -> Reservationsanfrage:
    anfrage = db.get(Reservationsanfrage, anfrage_id)
    if not anfrage:
        raise HTTPException(404, "Reservationsanfrage nicht gefunden")
    if not anfrage.vollstaendig:
        raise HTTPException(400, f"Anfrage ist unvollständig ({anfrage.fehlende_angaben}) – zuerst Angaben ergänzen")
    return anfrage


@router.post("/{anfrage_id}/antwort/vorbereiten", response_model=AntwortEntwurf)
def antwort_vorbereiten(anfrage_id: uuid.UUID, daten: AntwortVorbereiten, db: Session = Depends(get_db)):
    """Füllt die Vorlage der gewählten Sprache aus. Es wird noch nichts gespeichert oder verschickt."""
    anfrage = _vollstaendige_anfrage(db, anfrage_id)
    am.startvorlagen_ergaenzen(db)
    vorlage = db.execute(
        select(EmailVorlage).where(EmailVorlage.typ == am.TYP_ERSTANTWORT, EmailVorlage.sprache == daten.sprache)
    ).scalar_one()
    betrieb = am.betriebsangaben(db)
    werte = am.werte_fuer(anfrage, daten.sprache, daten.betrag, daten.zahlungsfrist, betrieb)
    betreff, u1 = am.ersetze(vorlage.betreff, werte)
    text, u2 = am.ersetze(vorlage.koerper, werte)
    warnungen = am.warnungen_betrieb(betrieb)
    if u1 or u2:
        warnungen.append("Unbekannte Platzhalter in der Vorlage: " + ", ".join(sorted(set(u1 + u2))))
    return AntwortEntwurf(vorlage_id=vorlage.id, sprache=daten.sprache, empfaenger=anfrage.gast_email,
                          betreff=betreff, text=text, warnungen=warnungen)


@router.post("/{anfrage_id}/antwort/gesendet", response_model=ReservationsanfrageDetail)
def antwort_als_gesendet_markieren(anfrage_id: uuid.UUID, daten: AntwortGesendet, db: Session = Depends(get_db)):
    """
    Hält fest, dass die Antwort (aus dem eigenen Mailprogramm) verschickt wurde:
    der endgültige Text wird protokolliert, der Status wechselt auf
    "Antwort gesendet". Sobald SMTP eingerichtet ist, verschickt die App selbst.
    """
    anfrage = _vollstaendige_anfrage(db, anfrage_id)
    if not db.get(EmailVorlage, daten.vorlage_id):
        raise HTTPException(400, "Vorlage nicht gefunden")
    db.add(EmailVersand(
        bezug_typ="reservationsanfrage", bezug_id=anfrage.id, vorlage_id=daten.vorlage_id,
        gesendet_von="Oberfläche (ohne Login)", empfaenger=anfrage.gast_email,
        betreff_final=daten.betreff, koerper_final=daten.text, status="gesendet",
        gesendet_am=datetime.now(timezone.utc),
    ))
    if anfrage.status in ("neu", "unvollstaendig", "geprueft_vollstaendig"):
        anfrage.status = "erstantwort_gesendet"
    db.commit()
    db.refresh(anfrage)
    return anfrage


@router.get("/{anfrage_id}/mails", response_model=list[VersandOut])
def mails_zur_anfrage(anfrage_id: uuid.UUID, db: Session = Depends(get_db)):
    return db.execute(
        select(EmailVersand)
        .where(EmailVersand.bezug_typ == "reservationsanfrage", EmailVersand.bezug_id == anfrage_id)
        .order_by(EmailVersand.gesendet_am.desc())
    ).scalars().all()
