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
from app.models.buchung import Aufenthalt, Buchung, BuchungLeistung, Gast
from app.models.reservation import Reservationsanfrage
from app.schemas.reservation import StellplatzTyp
from app.services import leistungen as lst

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
    buchung.leistungen = lst.grundzeilen(buchung)
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
    lst.zeitraum_setzen(b, b.von, tag)
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
    bemerkung: str | None = None


_GAST_FELDER = ("vorname", "nachname", "nationalitaet", "geburtsdatum", "strasse", "plz", "ort", "land", "email", "telefon")
_PFLICHT = ("vorname", "nachname", "nationalitaet", "stellplatz_typ", "von", "bis")


@router.patch("/{buchung_id}", response_model=AufenthaltDetail)
def aendern(buchung_id: uuid.UUID, daten: AufenthaltAenderung, db: Session = Depends(get_db)):
    """
    Aufenthalt korrigieren, verlängern oder verkürzen. Bei neuem Zeitraum ziehen
    die Leistungen mit (siehe app/services/leistungen.py); die Belegung rechnet
    automatisch mit. Leere Texte löschen ein freiwilliges Feld; Name,
    Nationalität, Typ und Daten bleiben Pflicht. Personen: über die Leistungen.
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
    neuer_typ = werte.pop("stellplatz_typ", None)
    if neuer_typ and neuer_typ != b.stellplatz_typ:
        lst.stellplatz_wechseln(b, neuer_typ)
    werte.pop("von", None), werte.pop("bis", None)
    for feld, wert in werte.items():
        if isinstance(wert, str):
            wert = wert.strip() or None
            if wert is None and feld in _PFLICHT:
                raise HTTPException(400, f"«{feld}» darf nicht leer sein")
        if feld in _GAST_FELDER:
            setattr(g, feld, wert)
        else:
            setattr(b, feld, wert)
    if (von, bis) != (b.von, b.bis):
        lst.zeitraum_setzen(b, von, bis)
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



# --- Leistungen ------------------------------------------------------------------

class LeistungOut(BaseModel):
    id: uuid.UUID
    art: str
    bezeichnung: str
    gruppe: str
    einheit: str
    anzahl: int
    von: date
    bis: date
    naechte: int
    menge: int
    kurtaxepflichtig: bool
    bemerkung: str | None


class TaxeOut(BaseModel):
    typ: str
    bezeichnung: str
    personennaechte: int
    betrag: str


class Leistungen(BaseModel):
    zeilen: list[LeistungOut]
    taxen: list[TaxeOut]
    personen_je_nacht: list[dict]
    arten: list[dict]


class LeistungEingabe(BaseModel):
    art: str
    anzahl: int = Field(default=1, ge=1, le=99)
    von: date
    bis: date | None = None
    """Bei Stückleistungen leer (= `von`)."""
    kurtaxepflichtig: bool = True
    bemerkung: str | None = Field(default=None, max_length=200)


class LeistungAenderung(BaseModel):
    anzahl: int | None = Field(default=None, ge=1, le=99)
    von: date | None = None
    bis: date | None = None
    kurtaxepflichtig: bool | None = None
    bemerkung: str | None = Field(default=None, max_length=200)


class Abwesenheit(BaseModel):
    anzahl: int = Field(ge=1, le=99)
    von: date
    """Erste Nacht, in der sie fehlen."""
    bis: date
    """Tag der Rückkehr."""


def _leistungen(db: Session, b: Buchung) -> Leistungen:
    zeilen = sorted(b.leistungen, key=lambda z: ([a.code for a in lst.ARTEN].index(z.art) if z.art in lst.ART else 99, z.von))
    return Leistungen(
        zeilen=[LeistungOut(
            id=z.id, art=z.art, bezeichnung=lst.ART[z.art].bezeichnung if z.art in lst.ART else z.art,
            gruppe=lst.ART[z.art].gruppe if z.art in lst.ART else "zusatz",
            einheit=lst.ART[z.art].einheit if z.art in lst.ART else "pro_nacht",
            anzahl=z.anzahl, von=z.von, bis=z.bis, naechte=z.naechte, menge=lst.menge(z),
            kurtaxepflichtig=z.kurtaxepflichtig, bemerkung=z.bemerkung) for z in zeilen],
        taxen=[TaxeOut(typ=t.typ, bezeichnung=t.bezeichnung, personennaechte=t.personennaechte, betrag=str(t.betrag))
               for t in lst.taxen(db, b)],
        personen_je_nacht=[{"datum": d, "erwachsene": v[0], "kinder": v[1], "kleinkinder": v[2]}
                           for d, v in lst.personen_je_nacht(b).items()],
        arten=[{"code": a.code, "bezeichnung": a.bezeichnung, "gruppe": a.gruppe, "einheit": a.einheit} for a in lst.ARTEN],
    )


def _aenderbar(b: Buchung) -> None:
    if b.rechnung is not None:
        raise HTTPException(400, "Zu diesem Aufenthalt gibt es bereits eine Rechnung – nicht mehr änderbar")


def _pruefe_zeitraum(b: Buchung, art: str, von: date, bis: date) -> None:
    if art not in lst.ART:
        raise HTTPException(400, f"Unbekannte Leistung «{art}»")
    if lst.ist_stueck(art):
        if not b.von <= von <= b.bis:
            raise HTTPException(400, "Das Datum muss im Aufenthalt liegen")
        return
    if bis <= von:
        raise HTTPException(400, "«Bis» muss nach «von» liegen")
    if von < b.von or bis > b.bis:
        raise HTTPException(400, "Die Leistung muss innerhalb des Aufenthalts liegen – sonst zuerst den Aufenthalt verlängern")


def _zeile(b: Buchung, leistung_id: uuid.UUID) -> BuchungLeistung:
    for z in b.leistungen:
        if z.id == leistung_id:
            return z
    raise HTTPException(404, "Leistung nicht gefunden")


@router.get("/{buchung_id}/leistungen", response_model=Leistungen)
def leistungen_lesen(buchung_id: uuid.UUID, db: Session = Depends(get_db)):
    return _leistungen(db, _buchung(db, buchung_id))


@router.post("/{buchung_id}/leistungen", response_model=Leistungen, status_code=201)
def leistung_hinzufuegen(buchung_id: uuid.UUID, daten: LeistungEingabe, db: Session = Depends(get_db)):
    """Z.B. zwei Personen mit eigenem Zelt vom 12. bis 14., Strom, Auto."""
    b = _buchung(db, buchung_id)
    _aenderbar(b)
    bis = daten.von if daten.art in lst.ART and lst.ist_stueck(daten.art) else (daten.bis or b.bis)
    _pruefe_zeitraum(b, daten.art, daten.von, bis)
    b.leistungen.append(BuchungLeistung(art=daten.art, anzahl=daten.anzahl, von=daten.von, bis=bis,
                                        kurtaxepflichtig=daten.kurtaxepflichtig,
                                        bemerkung=(daten.bemerkung or "").strip() or None))
    lst.zaehler_nachfuehren(b)
    db.commit()
    db.refresh(b)
    return _leistungen(db, b)


@router.patch("/{buchung_id}/leistungen/{leistung_id}", response_model=Leistungen)
def leistung_aendern(buchung_id: uuid.UUID, leistung_id: uuid.UUID, daten: LeistungAenderung, db: Session = Depends(get_db)):
    b = _buchung(db, buchung_id)
    _aenderbar(b)
    z = _zeile(b, leistung_id)
    werte = daten.model_dump(exclude_unset=True)
    von = werte.get("von") or z.von
    bis = von if lst.ist_stueck(z.art) else (werte.get("bis") or z.bis)
    _pruefe_zeitraum(b, z.art, von, bis)
    z.von, z.bis = von, bis
    if werte.get("anzahl"):
        z.anzahl = werte["anzahl"]
    if werte.get("kurtaxepflichtig") is not None:
        z.kurtaxepflichtig = werte["kurtaxepflichtig"]
    if "bemerkung" in werte:
        z.bemerkung = (werte["bemerkung"] or "").strip() or None
    lst.zaehler_nachfuehren(b)
    db.commit()
    db.refresh(b)
    return _leistungen(db, b)


@router.post("/{buchung_id}/leistungen/{leistung_id}/abwesenheit", response_model=Leistungen)
def abwesenheit_erfassen(buchung_id: uuid.UUID, leistung_id: uuid.UUID, daten: Abwesenheit, db: Session = Depends(get_db)):
    """Z.B. 2 von 4 Kindern sind zwei Nächte nicht auf dem Platz: die Zeile wird aufgeteilt."""
    b = _buchung(db, buchung_id)
    _aenderbar(b)
    try:
        lst.abwesenheit(b, _zeile(b, leistung_id), daten.anzahl, daten.von, daten.bis)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    db.commit()
    db.refresh(b)
    return _leistungen(db, b)


@router.delete("/{buchung_id}/leistungen/{leistung_id}", response_model=Leistungen)
def leistung_loeschen(buchung_id: uuid.UUID, leistung_id: uuid.UUID, db: Session = Depends(get_db)):
    b = _buchung(db, buchung_id)
    _aenderbar(b)
    b.leistungen.remove(_zeile(b, leistung_id))
    lst.zaehler_nachfuehren(b)
    db.commit()
    db.refresh(b)
    return _leistungen(db, b)
