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
from typing import Literal
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.models.kommunikation import EmailVersand, EmailVorlage, MailNachricht
from app.models.reservation import Reservationsanfrage, Zahlung
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
    from dataclasses import asdict

    return asdict(ergebnis)


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
        raise HTTPException(422, "Mail enthält keinen verwertbaren Absender, ist eine automatische Nachricht "
                                 "oder eine eigene Antwort ohne passende Anfrage")
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
    anfragen = db.execute(stmt).scalars().all()
    neue = _neue_mails(db)
    return [ReservationsanfrageOut.model_validate(a).model_copy(update={"neue_mails": neue.get(a.id, 0)})
            for a in anfragen]


def _neue_mails(db: Session, anfrage_id: uuid.UUID | None = None) -> dict:
    stmt = (select(MailNachricht.reservationsanfrage_id, func.count())
            .where(MailNachricht.gelesen.is_(False), MailNachricht.reservationsanfrage_id.is_not(None))
            .group_by(MailNachricht.reservationsanfrage_id))
    if anfrage_id:
        stmt = stmt.where(MailNachricht.reservationsanfrage_id == anfrage_id)
    return dict(db.execute(stmt).all())


def _anzahlungen(db: Session, anfrage_id: uuid.UUID) -> list[Zahlung]:
    return list(db.execute(
        select(Zahlung).where(Zahlung.bezug_typ == "reservationsanfrage", Zahlung.bezug_id == anfrage_id,
                              Zahlung.status == "eingegangen").order_by(Zahlung.eingegangen_am)
    ).scalars())


def _detail(db: Session, anfrage: Reservationsanfrage) -> ReservationsanfrageDetail:
    zahlungen = _anzahlungen(db, anfrage.id)
    letzte = zahlungen[-1] if zahlungen else None
    return ReservationsanfrageDetail.model_validate(anfrage).model_copy(update={
        "neue_mails": _neue_mails(db, anfrage.id).get(anfrage.id, 0),
        "anzahlung_erhalten": sum((Decimal(z.betrag) for z in zahlungen), Decimal("0")) if zahlungen else None,
        "anzahlung_eingegangen_am": letzte.eingegangen_am.date() if letzte and letzte.eingegangen_am else None,
        "anzahlung_zahlungsart": letzte.zahlungsart if letzte else None,
    })


@router.get("/{anfrage_id}", response_model=ReservationsanfrageDetail)
def anfrage_lesen(anfrage_id: uuid.UUID, db: Session = Depends(get_db)):
    anfrage = db.get(Reservationsanfrage, anfrage_id)
    if not anfrage:
        raise HTTPException(404, "Reservationsanfrage nicht gefunden")
    return _detail(db, anfrage)


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
    return _detail(db, anfrage)


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
    return _detail(db, anfrage)


class Akzeptieren(BaseModel):
    betrag: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    """Tatsächlich gutgeschriebener Betrag in CHF (z.B. bei Zahlung in Euro). Leer oder 0:
    ohne Anzahlung akzeptiert (z.B. Stammgäste)."""
    zahlungsart: Literal["bankueberweisung", "twint", "bar", "kreditkarte"] = "bankueberweisung"
    eingegangen_am: date | None = None


_AKZEPTIERBAR = {"geprueft_vollstaendig", "in_abklaerung", "erstantwort_gesendet", "zahlung_ausstehend"}


@router.post("/{anfrage_id}/zahlung-bestaetigen", response_model=ReservationsanfrageDetail)
def zahlung_bestaetigen(anfrage_id: uuid.UUID, daten: Akzeptieren | None = None, db: Session = Depends(get_db)):
    """
    Akzeptiert die Reservation (Konzept Abschnitt 10.5) und hält die
    gutgeschriebene Anzahlung als Zahlung fest – mit dem genauen Betrag in CHF,
    der später in der Rechnung abgezogen wird. Ohne Betrag: akzeptiert ohne
    Anzahlung.

    HINWEIS: Erzeugt bewusst NOCH KEINE Buchung (Stellplatz-Zuteilung erfolgt
    ausserhalb des Tools).
    """
    daten = daten or Akzeptieren()
    anfrage = _vollstaendige_anfrage(db, anfrage_id)
    if anfrage.status not in _AKZEPTIERBAR:
        raise HTTPException(400, "Diese Anfrage kann in ihrem Status nicht akzeptiert werden")
    if daten.betrag:
        eingang = daten.eingegangen_am or date.today()
        db.add(Zahlung(
            bezug_typ="reservationsanfrage", bezug_id=anfrage.id, betrag=daten.betrag, waehrung="CHF",
            zahlungsart=daten.zahlungsart, status="eingegangen", referenz=anfrage.nummer,
            eingegangen_am=datetime(eingang.year, eingang.month, eingang.day, 12, tzinfo=timezone.utc),
            abgeglichen_von="Oberfläche (ohne Login)",
        ))
    anfrage.status = "bezahlt_akzeptiert"
    db.commit()
    db.refresh(anfrage)
    return _detail(db, anfrage)


# --- Antwort mit Zahlungsinformationen (Konzept 10.2) ------------------------------

class AntwortVorbereiten(BaseModel):
    typ: Literal["erstantwort_zahlungsinfo", "freie_antwort", "bestaetigung_definitiv"] = "erstantwort_zahlungsinfo"
    sprache: str = Field(pattern="^(de|fr|it|en)$")
    betrag: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    """Pflicht bei der Antwort mit Anzahlung, bei der freien Antwort ohne Bedeutung."""
    zahlungsfrist: date | None = None


class AntwortEntwurf(BaseModel):
    vorlage_id: uuid.UUID
    typ: str
    sprache: str
    empfaenger: str
    betreff: str
    text: str
    warnungen: list[str]
    einfuege_position: int | None = None
    """Freie Antwort: Stelle nach der Anrede, an der der eigene Text beginnt."""


class AntwortGesendet(BaseModel):
    vorlage_id: uuid.UUID
    betrag: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    """Antwort mit Anzahlung: verlangter Betrag, wird beim Akzeptieren vorgeschlagen."""
    betreff: str = Field(min_length=1, max_length=300)
    text: str = Field(min_length=1, max_length=50000)


class VerlaufEintrag(BaseModel):
    id: uuid.UUID
    richtung: str
    """eingang | ausgang"""
    quelle: str
    """tool (im Tool vorbereitet) | postfach (aus dem Tool-Postfach)"""
    datum: datetime
    von: str
    an: str | None
    betreff: str
    text: str
    gelesen: bool
    weitergeleitet: bool


def _vollstaendige_anfrage(db: Session, anfrage_id: uuid.UUID) -> Reservationsanfrage:
    anfrage = db.get(Reservationsanfrage, anfrage_id)
    if not anfrage:
        raise HTTPException(404, "Reservationsanfrage nicht gefunden")
    if not anfrage.vollstaendig:
        raise HTTPException(400, f"Anfrage ist unvollständig ({anfrage.fehlende_angaben}) – zuerst Angaben ergänzen")
    return anfrage


def _anfrage(db: Session, anfrage_id: uuid.UUID) -> Reservationsanfrage:
    anfrage = db.get(Reservationsanfrage, anfrage_id)
    if not anfrage:
        raise HTTPException(404, "Reservationsanfrage nicht gefunden")
    return anfrage


@router.post("/{anfrage_id}/antwort/vorbereiten", response_model=AntwortEntwurf)
def antwort_vorbereiten(anfrage_id: uuid.UUID, daten: AntwortVorbereiten, db: Session = Depends(get_db)):
    """
    Füllt die Vorlage der gewählten Art und Sprache aus. Es wird noch nichts
    gespeichert oder verschickt. Die Antwort mit Anzahlung braucht eine
    vollständige Anfrage und einen Betrag; die freie Antwort geht immer.
    """
    mit_anzahlung = daten.typ == am.TYP_ERSTANTWORT
    anfrage = _anfrage(db, anfrage_id) if daten.typ == am.TYP_FREI else _vollstaendige_anfrage(db, anfrage_id)
    if mit_anzahlung and daten.betrag is None:
        raise HTTPException(422, "Bitte die Anzahlung angeben")
    if daten.typ == am.TYP_BESTAETIGUNG and anfrage.status != "bezahlt_akzeptiert":
        raise HTTPException(400, "Die Bestätigung gibt es erst, wenn die Reservation akzeptiert ist")
    zahlungen = _anzahlungen(db, anfrage.id)
    erhalten = sum((Decimal(z.betrag) for z in zahlungen), Decimal("0")) or None
    am.startvorlagen_ergaenzen(db)
    vorlage = db.execute(
        select(EmailVorlage).where(EmailVorlage.typ == daten.typ, EmailVorlage.sprache == daten.sprache)
    ).scalar_one()
    betrieb = am.betriebsangaben(db)
    werte = am.werte_fuer(anfrage, daten.sprache, daten.betrag if mit_anzahlung else None,
                          daten.zahlungsfrist, betrieb, am.letzter_gast_betreff(db, anfrage), erhalten)
    betreff, u1 = am.ersetze(vorlage.betreff, werte)
    betreff = am.betreff_mit_nummer(betreff, anfrage.nummer, daten.sprache)
    text, u2 = am.ersetze(vorlage.koerper, werte)
    warnungen = am.warnungen_betrieb(betrieb, daten.typ)
    if u1 or u2:
        warnungen.append("Unbekannte Platzhalter in der Vorlage: " + ", ".join(sorted(set(u1 + u2))))
    position = None
    if not mit_anzahlung:
        absatz = text.find("\n\n")
        position = absatz + 2 if absatz >= 0 else len(text)
    return AntwortEntwurf(vorlage_id=vorlage.id, typ=daten.typ, sprache=daten.sprache, empfaenger=anfrage.gast_email,
                          betreff=betreff, text=text, warnungen=warnungen, einfuege_position=position)


@router.post("/{anfrage_id}/antwort/gesendet", response_model=ReservationsanfrageDetail)
def antwort_als_gesendet_markieren(anfrage_id: uuid.UUID, daten: AntwortGesendet, db: Session = Depends(get_db)):
    """
    Hält fest, dass die Antwort (aus dem eigenen Mailprogramm) verschickt wurde:
    der endgültige Text wird protokolliert. Status: Antwort mit Anzahlung ->
    "Antwort gesendet", freie Antwort -> "In Abklärung" (siehe
    antwortmail.status_nach_antwort). Sobald SMTP eingerichtet ist, verschickt
    die App selbst.
    """
    vorlage = db.get(EmailVorlage, daten.vorlage_id)
    if not vorlage:
        raise HTTPException(400, "Vorlage nicht gefunden")
    mit_anzahlung = vorlage.typ == am.TYP_ERSTANTWORT
    anfrage = _anfrage(db, anfrage_id) if vorlage.typ == am.TYP_FREI else _vollstaendige_anfrage(db, anfrage_id)
    if mit_anzahlung and daten.betrag:
        anfrage.anzahlung_verlangt = daten.betrag
    db.add(EmailVersand(
        bezug_typ="reservationsanfrage", bezug_id=anfrage.id, vorlage_id=daten.vorlage_id,
        gesendet_von="Oberfläche (ohne Login)", empfaenger=anfrage.gast_email,
        betreff_final=daten.betreff, koerper_final=daten.text, status="gesendet",
        gesendet_am=datetime.now(timezone.utc),
    ))
    if vorlage.typ != am.TYP_BESTAETIGUNG:
        am.status_nach_antwort(anfrage, mit_anzahlung)
    db.commit()
    db.refresh(anfrage)
    return _detail(db, anfrage)


def _utc(d: datetime) -> datetime:
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


@router.get("/{anfrage_id}/mails", response_model=list[VerlaufEintrag])
def mails_zur_anfrage(anfrage_id: uuid.UUID, db: Session = Depends(get_db)):
    """Mailverlauf der Anfrage, neueste zuerst: im Tool vorbereitete Antworten und Mails aus dem Postfach."""
    eintraege = [
        VerlaufEintrag(id=v.id, richtung="ausgang", quelle="tool", datum=_utc(v.gesendet_am), von=v.gesendet_von,
                       an=v.empfaenger, betreff=v.betreff_final, text=v.koerper_final, gelesen=True, weitergeleitet=False)
        for v in db.execute(select(EmailVersand).where(EmailVersand.bezug_typ == "reservationsanfrage",
                                                       EmailVersand.bezug_id == anfrage_id)).scalars()
    ]
    eintraege += [
        VerlaufEintrag(id=n.id, richtung=n.richtung, quelle="postfach", datum=_utc(n.datum), von=n.von, an=n.an,
                       betreff=n.betreff, text=n.text, gelesen=n.gelesen, weitergeleitet=n.weitergeleitet)
        for n in db.execute(select(MailNachricht).where(MailNachricht.reservationsanfrage_id == anfrage_id)).scalars()
    ]
    return sorted(eintraege, key=lambda e: e.datum, reverse=True)


@router.post("/{anfrage_id}/mails/gelesen", status_code=204)
def mails_gelesen(anfrage_id: uuid.UUID, db: Session = Depends(get_db)):
    """Markiert neue Mails des Gastes als gelesen (beim Öffnen der Anfrage)."""
    db.execute(update(MailNachricht).where(MailNachricht.reservationsanfrage_id == anfrage_id,
                                           MailNachricht.gelesen.is_(False)).values(gelesen=True))
    db.commit()
