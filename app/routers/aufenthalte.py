"""
Check-in in der Belegung: Buchung & Aufenthalt erfassen.

- Aus einer akzeptierten Reservation am Anreisetag (oder danach, falls
  nachgetragen): Gast, Buchung und Aufenthalt entstehen in einem Schritt, die
  Reservation erhält den Status «angereist».
- Ohne Reservation (z.B. Nebensaison, Gast steht vor der Tür).

Pflicht sind Name und Nationalität (für die HESTA-Meldung); die Adresse ist
optional. Die Stellplatz-Zuteilung erfolgt ausserhalb des Tools; erfasst
werden der Stellplatz-Typ und optional die Platznummer als Freitext.
"""
import uuid
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.buchung import Aufenthalt, Buchung, Gast
from app.models.reservation import Reservationsanfrage
from app.schemas.reservation import StellplatzTyp

router = APIRouter(prefix="/aufenthalte", tags=["Aufenthalte"])


class CheckIn(BaseModel):
    reservationsanfrage_id: uuid.UUID | None = None
    vorname: str = Field(min_length=1, max_length=100)
    nachname: str = Field(min_length=1, max_length=100)
    strasse: str | None = Field(default=None, max_length=200)
    plz: str | None = Field(default=None, max_length=20)
    ort: str | None = Field(default=None, max_length=100)
    land: str | None = Field(default=None, pattern="^[A-Z]{2}$")
    """Land der Adresse, optional."""
    nationalitaet: str = Field(pattern="^[A-Z]{2}$")
    """Pflicht: ISO-Ländercode, wird für die HESTA-Meldung gebraucht."""
    email: EmailStr | None = None
    telefon: str | None = Field(default=None, max_length=50)
    stellplatz_typ: StellplatzTyp
    platz: str | None = Field(default=None, max_length=50)
    von: date
    bis: date
    anzahl_erwachsene: int = Field(default=1, ge=0, le=50)
    anzahl_kinder: int = Field(default=0, ge=0, le=50)
    """Kinder 6–15 Jahre."""
    anzahl_kleinkinder: int = Field(default=0, ge=0, le=50)
    """Kleinkinder 0–5 Jahre."""
    bemerkung: str | None = None


class AufenthaltDetail(BaseModel):
    buchung_id: uuid.UUID
    reservationsanfrage_id: uuid.UUID | None
    gast_id: uuid.UUID
    vorname: str
    nachname: str
    strasse: str | None
    plz: str | None
    ort: str | None
    land: str | None
    nationalitaet: str | None
    email: str | None
    telefon: str | None
    stellplatz_typ: str | None
    platz: str | None
    von: date
    bis: date
    anzahl_erwachsene: int
    anzahl_kinder: int
    anzahl_kleinkinder: int
    status: str
    bemerkung: str | None
    geburtsdatum: date | None = None
    hat_rechnung: bool = False
    reservationsnummer: str | None = None


def _detail(b: Buchung, db: Session | None = None) -> AufenthaltDetail:
    g = b.hauptgast
    anfrage = db.get(Reservationsanfrage, b.reservationsanfrage_id) if db is not None and b.reservationsanfrage_id else None
    return AufenthaltDetail(
        buchung_id=b.id, reservationsanfrage_id=b.reservationsanfrage_id, gast_id=g.id, vorname=g.vorname,
        nachname=g.nachname, strasse=g.strasse, plz=g.plz, ort=g.ort, land=g.land, nationalitaet=g.nationalitaet, email=g.email, telefon=g.telefon,
        stellplatz_typ=b.stellplatz_typ, platz=b.platz, von=b.von, bis=b.bis, anzahl_erwachsene=b.anzahl_erwachsene,
        anzahl_kinder=b.anzahl_kinder, anzahl_kleinkinder=b.anzahl_kleinkinder or 0, status=b.status,
        bemerkung=b.bemerkung, geburtsdatum=g.geburtsdatum, hat_rechnung=b.rechnung is not None,
        reservationsnummer=anfrage.nummer if anfrage else None,
    )


def _buchung(db: Session, buchung_id: uuid.UUID) -> Buchung:
    b = db.get(Buchung, buchung_id)
    if not b:
        raise HTTPException(404, "Aufenthalt nicht gefunden")
    return b


@router.post("", response_model=AufenthaltDetail, status_code=201)
def einchecken(daten: CheckIn, db: Session = Depends(get_db)):
    if daten.bis <= daten.von:
        raise HTTPException(400, "Die Abreise muss nach der Anreise liegen")
    if daten.von > date.today():
        raise HTTPException(400, "Einchecken geht erst am Anreisetag")
    anfrage = None
    if daten.reservationsanfrage_id:
        anfrage = db.get(Reservationsanfrage, daten.reservationsanfrage_id)
        if not anfrage:
            raise HTTPException(404, "Reservationsanfrage nicht gefunden")
        if anfrage.status not in ("bezahlt_akzeptiert", "nicht_erschienen"):
            raise HTTPException(400, "Nur akzeptierte Reservationen können eingecheckt werden")
        if anfrage.gewuenscht_von and anfrage.gewuenscht_von > date.today():
            raise HTTPException(400, "Einchecken geht erst am Anreisetag")

    gast = Gast(vorname=daten.vorname.strip(), nachname=daten.nachname.strip(), strasse=daten.strasse,
                plz=daten.plz, ort=daten.ort, land=daten.land, nationalitaet=daten.nationalitaet,
                email=daten.email or (anfrage.gast_email if anfrage else None),
                telefon=daten.telefon or (anfrage.gast_telefon if anfrage else None))
    db.add(gast)
    db.flush()
    buchung = Buchung(
        stellplatz_typ=daten.stellplatz_typ, platz=(daten.platz or "").strip() or None, von=daten.von, bis=daten.bis,
        anzahl_erwachsene=daten.anzahl_erwachsene, anzahl_kinder=daten.anzahl_kinder,
        anzahl_kleinkinder=daten.anzahl_kleinkinder, bemerkung=daten.bemerkung,
        status="eingecheckt", hauptgast_id=gast.id, reservationsanfrage_id=anfrage.id if anfrage else None,
    )
    db.add(buchung)
    db.flush()
    db.add(Aufenthalt(buchung_id=buchung.id, gast_id=gast.id, ankunft=daten.von, abreise=daten.bis))
    if anfrage:
        anfrage.status = "angereist"
    db.commit()
    db.refresh(buchung)
    return _detail(buchung, db)


@router.get("", response_model=list[AufenthaltDetail])
def auflisten(status: Literal["eingecheckt", "ausgecheckt", "alle"] = "alle",
              von: date | None = None, bis: date | None = None, db: Session = Depends(get_db)):
    """
    Aufenthalte, wahlweise nach Status und Zeitraum (berührt [von, bis]).
    Eingecheckte zuerst nach Abreise, abgereiste nach Abreise absteigend.
    """
    stmt = select(Buchung).where(Buchung.status.in_(
        ("eingecheckt", "ausgecheckt") if status == "alle" else (status,)))
    if von:
        stmt = stmt.where(Buchung.bis >= von)
    if bis:
        stmt = stmt.where(Buchung.von <= bis)
    buchungen = list(db.execute(stmt).scalars())
    buchungen.sort(key=lambda b: (b.status != "eingecheckt", b.bis if b.status == "eingecheckt" else -b.bis.toordinal(), b.von))
    return [_detail(b, db) for b in buchungen]


@router.get("/{buchung_id}", response_model=AufenthaltDetail)
def lesen(buchung_id: uuid.UUID, db: Session = Depends(get_db)):
    return _detail(_buchung(db, buchung_id), db)


class Abreise(BaseModel):
    datum: date | None = None
    """Tatsächlicher Abreisetag; Standard heute. Gibt den Platz ab diesem Tag frei."""


@router.post("/{buchung_id}/abreise", response_model=AufenthaltDetail)
def abreisen(buchung_id: uuid.UUID, daten: Abreise | None = None, db: Session = Depends(get_db)):
    b = _buchung(db, buchung_id)
    if b.status != "eingecheckt":
        raise HTTPException(400, "Nur eingecheckte Aufenthalte können abreisen")
    tag = (daten.datum if daten and daten.datum else None) or date.today()
    if tag <= b.von:
        tag = b.von + timedelta(days=1)
    b.bis = tag
    for a in b.aufenthalte:
        a.abreise = min(a.abreise, tag) if a.abreise > a.ankunft else tag
    b.status = "ausgecheckt"
    db.commit()
    db.refresh(b)
    return _detail(b, db)


class AufenthaltAenderung(BaseModel):
    """Korrekturen am Aufenthalt: nur die mitgeschickten Felder werden geändert."""
    vorname: str | None = Field(default=None, min_length=1, max_length=100)
    nachname: str | None = Field(default=None, min_length=1, max_length=100)
    nationalitaet: str | None = Field(default=None, pattern="^[A-Z]{2}$")
    geburtsdatum: date | None = None
    strasse: str | None = Field(default=None, max_length=200)
    plz: str | None = Field(default=None, max_length=20)
    ort: str | None = Field(default=None, max_length=100)
    land: str | None = Field(default=None, pattern="^[A-Z]{2}$")
    email: EmailStr | None = None
    telefon: str | None = Field(default=None, max_length=50)
    stellplatz_typ: StellplatzTyp | None = None
    platz: str | None = Field(default=None, max_length=50)
    von: date | None = None
    bis: date | None = None
    anzahl_erwachsene: int | None = Field(default=None, ge=0, le=50)
    anzahl_kinder: int | None = Field(default=None, ge=0, le=50)
    anzahl_kleinkinder: int | None = Field(default=None, ge=0, le=50)
    bemerkung: str | None = None


_GAST_FELDER = ("vorname", "nachname", "nationalitaet", "geburtsdatum", "strasse", "plz", "ort", "land", "email", "telefon")
_PFLICHT = ("vorname", "nachname", "nationalitaet", "stellplatz_typ", "von", "bis",
            "anzahl_erwachsene", "anzahl_kinder", "anzahl_kleinkinder")


@router.patch("/{buchung_id}", response_model=AufenthaltDetail)
def aendern(buchung_id: uuid.UUID, daten: AufenthaltAenderung, db: Session = Depends(get_db)):
    """
    Aufenthalt korrigieren oder verlängern (neues Abreisedatum). Die Belegung
    rechnet automatisch mit den neuen Daten. Leere Texte löschen ein
    freiwilliges Feld; Name, Nationalität, Typ, Daten und Personen bleiben Pflicht.
    """
    b = _buchung(db, buchung_id)
    if b.rechnung is not None:
        raise HTTPException(400, "Zu diesem Aufenthalt gibt es bereits eine Rechnung – nicht mehr änderbar")
    werte = daten.model_dump(exclude_unset=True)
    for feld in _PFLICHT:
        if feld in werte and werte[feld] is None:
            raise HTTPException(400, f"«{feld}» darf nicht leer sein")
    von, bis = werte.get("von", b.von), werte.get("bis", b.bis)
    if bis <= von:
        raise HTTPException(400, "Die Abreise muss nach der Anreise liegen")
    if von > date.today():
        raise HTTPException(400, "Die Anreise kann nicht in der Zukunft liegen")
    g = b.hauptgast
    for feld, wert in werte.items():
        if isinstance(wert, str):
            wert = wert.strip() or None
            if wert is None and feld in _PFLICHT:
                raise HTTPException(400, f"«{feld}» darf nicht leer sein")
        if feld in _GAST_FELDER:
            setattr(g, feld, wert)
        else:
            setattr(b, feld, wert)
    for a in b.aufenthalte:
        if a.gast_id == b.hauptgast_id:
            a.ankunft, a.abreise = von, bis
    db.commit()
    db.refresh(b)
    return _detail(b, db)


@router.post("/{buchung_id}/abreise-zuruecknehmen", response_model=AufenthaltDetail)
def abreise_zuruecknehmen(buchung_id: uuid.UUID, db: Session = Depends(get_db)):
    """Irrtümlich erfasste Abreise rückgängig machen: der Gast ist wieder auf dem Platz."""
    b = _buchung(db, buchung_id)
    if b.status != "ausgecheckt":
        raise HTTPException(400, "Nur abgereiste Aufenthalte")
    if b.rechnung is not None:
        raise HTTPException(400, "Zu diesem Aufenthalt gibt es bereits eine Rechnung")
    b.status = "eingecheckt"
    db.commit()
    db.refresh(b)
    return _detail(b, db)


@router.delete("/{buchung_id}", status_code=204)
def loeschen(buchung_id: uuid.UUID, db: Session = Depends(get_db)):
    """Irrtümlich erfassten Aufenthalt löschen; eine zugehörige Reservation ist wieder «akzeptiert»."""
    b = _buchung(db, buchung_id)
    if b.rechnung is not None:
        raise HTTPException(400, "Zu diesem Aufenthalt gibt es eine Rechnung – nicht löschbar")
    if b.reservationsanfrage_id:
        anfrage = db.get(Reservationsanfrage, b.reservationsanfrage_id)
        if anfrage and anfrage.status == "angereist":
            anfrage.status = "bezahlt_akzeptiert"
    gast_id = b.hauptgast_id
    for a in list(b.aufenthalte):
        db.delete(a)
    db.delete(b)
    db.flush()
    # Gast nur löschen, wenn er sonst nirgends vorkommt
    if not db.execute(select(Buchung).where(Buchung.hauptgast_id == gast_id)).first() and \
            not db.execute(select(Aufenthalt).where(Aufenthalt.gast_id == gast_id)).first():
        gast = db.get(Gast, gast_id)
        if gast:
            db.delete(gast)
    db.commit()
