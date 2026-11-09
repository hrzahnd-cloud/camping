"""
Rechnungen (Konzeptdokument Abschnitte 9.4, 12, 14).

POST /rechnungen erwartet eine explizite Liste von Positionen
(artikel_id + menge) statt diese vollautomatisch aus den Aufenthalten
abzuleiten – welche Artikel/Mengen genau auf eine Rechnung kommen
(z.B. wie Personen- und Stellplatz-Positionen kombiniert werden), ist
eine fachliche Entscheidung, die im Detail noch mit euch abzustimmen
ist. Die Preisfindung je Position (Saison, MWST) übernimmt das System.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models.artikel import Artikel, ArtikelPreis, Saison
from app.models.buchung import Buchung
from app.models.rechnung import Rechnung, Rechnungsposition
from app.schemas.rechnung import RechnungOut, RechnungspositionCreate
from app.services.mwst import zahl_text, mwst_betrag_aus_brutto, prozent_fuer_artikel
from app.services import antwortmail as am
from app.services import logo
from app.services import rechnung_aufenthalt as ra
from app.services.pdf_rechnung import RechnungsDaten, RechnungsPositionZeile, rechnung_pdf
from app.services.rechnungsnummer import naechste_rechnungsnummer
from app.services.taxen import berechne_taxen_fuer_buchung

router = APIRouter(prefix="/rechnungen", tags=["Rechnungen"])



def _ermittle_preis_und_mwst(db: Session, artikel: Artikel, stichtag: date) -> tuple[Decimal, Decimal]:
    """Liefert (preis, mwstsatz_prozent) für einen Artikel an einem Stichtag."""
    saison = db.execute(
        select(Saison).where(Saison.gueltig_ab <= stichtag, Saison.gueltig_bis >= stichtag)
    ).scalars().first()

    preis_row = None
    if saison:
        preis_row = db.execute(
            select(ArtikelPreis).where(
                ArtikelPreis.artikel_id == artikel.id, ArtikelPreis.saison_id == saison.id
            )
        ).scalar_one_or_none()
    if preis_row is None:
        preis_row = db.execute(
            select(ArtikelPreis).where(
                ArtikelPreis.artikel_id == artikel.id, ArtikelPreis.saison_id.is_(None)
            )
        ).scalar_one_or_none()
    if preis_row is None:
        raise HTTPException(400, f"Kein Preis für Artikel '{artikel.bezeichnung}' am {stichtag} hinterlegt")

    try:
        prozent = prozent_fuer_artikel(db, artikel, stichtag)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return Decimal(str(preis_row.preis)), prozent


@router.get("/taxen-vorschau")
def taxen_vorschau(buchung_id: uuid.UUID, db: Session = Depends(get_db)):
    """Kurtaxe und Beherbergungsabgabe einer Buchung, wie sie auf der Rechnung erscheinen würden."""
    buchung = db.get(Buchung, buchung_id)
    if not buchung:
        raise HTTPException(404, "Buchung nicht gefunden")
    ergebnis = berechne_taxen_fuer_buchung(db, buchung)
    return {
        "positionen": [
            {
                "bezeichnung": p.bezeichnung, "personennaechte": p.personennaechte,
                "einzelpreis": float(p.einzelpreis), "betrag": float(p.betrag),
            }
            for p in ergebnis.positionen
        ],
        "total": float(ergebnis.total),
        "warnungen": ergebnis.warnungen,
    }


@router.post("", response_model=RechnungOut, status_code=201)
def rechnung_erstellen(
    buchung_id: uuid.UUID,
    positionen: list[RechnungspositionCreate],
    mit_taxen: bool = True,
    db: Session = Depends(get_db),
):
    """
    Erstellt die Rechnung aus den übergebenen Positionen. Kurtaxe und
    Beherbergungsabgabe werden automatisch aus Aufenthalten (Nächte, Alter
    der Gäste) berechnet und angefügt (`mit_taxen=false` schaltet das ab).
    Sind unter den übergebenen Positionen bereits Taxen-Artikel, werden
    keine zusätzlichen berechnet, damit nichts doppelt verrechnet wird.
    """
    buchung = db.get(Buchung, buchung_id)
    if not buchung:
        raise HTTPException(404, "Buchung nicht gefunden")
    if not positionen:
        raise HTTPException(400, "Mindestens eine Rechnungsposition erforderlich")

    heute = date.today()

    rechnung = Rechnung(
        buchung_id=buchung.id,
        kunde_id=buchung.hauptgast_id,
        nummer=naechste_rechnungsnummer(db, heute.year),
        datum=heute,
        status="offen",
        gesamtbetrag=Decimal("0"),
        mwst_betrag_total=Decimal("0"),
    )
    db.add(rechnung)
    db.flush()

    gesamt = Decimal("0")
    mwst_gesamt = Decimal("0")
    taxen_schon_enthalten = False

    for pos_input in positionen:
        artikel = db.get(Artikel, pos_input.artikel_id)
        if not artikel:
            raise HTTPException(404, f"Artikel {pos_input.artikel_id} nicht gefunden")
        taxen_schon_enthalten = taxen_schon_enthalten or artikel.kategorie == "taxe"

        einzelpreis, mwst_prozent = _ermittle_preis_und_mwst(db, artikel, heute)
        menge = Decimal(str(pos_input.menge))
        betrag = (einzelpreis * menge).quantize(Decimal("0.01"))
        mwst_betrag = mwst_betrag_aus_brutto(betrag, mwst_prozent)

        db.add(Rechnungsposition(
            rechnung_id=rechnung.id,
            artikel_id=artikel.id,
            menge=menge,
            einzelpreis=einzelpreis,
            betrag=betrag,
            mwstsatz_prozent=mwst_prozent,
            mwst_betrag=mwst_betrag,
        ))
        gesamt += betrag
        mwst_gesamt += mwst_betrag

    if mit_taxen and not taxen_schon_enthalten:
        for tax in berechne_taxen_fuer_buchung(db, buchung).positionen:
            artikel = db.execute(select(Artikel).where(Artikel.code == tax.artikel_code)).scalar_one_or_none()
            if artikel is None:
                raise HTTPException(
                    400, f"Taxen-Artikel '{tax.artikel_code}' fehlt (Grunddaten einspielen: python -m app.seed)"
                )
            mwst_prozent = Decimal(str(artikel.mwstsatz.satz_prozent))
            mwst_betrag = mwst_betrag_aus_brutto(tax.betrag, mwst_prozent)
            db.add(Rechnungsposition(
                rechnung_id=rechnung.id,
                artikel_id=artikel.id,
                menge=Decimal(tax.personennaechte),
                einzelpreis=tax.einzelpreis,
                betrag=tax.betrag,
                mwstsatz_prozent=mwst_prozent,
                mwst_betrag=mwst_betrag,
            ))
            gesamt += tax.betrag
            mwst_gesamt += mwst_betrag

    rechnung.gesamtbetrag = gesamt
    rechnung.mwst_betrag_total = mwst_gesamt

    db.commit()
    db.refresh(rechnung)
    return db.execute(
        select(Rechnung)
        .options(selectinload(Rechnung.positionen))
        .where(Rechnung.id == rechnung.id)
    ).scalar_one()


# --- Rechnungen aus dem Aufenthalt (Modul «Rechnungen») ------------------------------

class RechnungsZeile(BaseModel):
    id: uuid.UUID
    nummer: str
    datum: date
    status: str
    gast_name: str
    buchung_id: uuid.UUID
    von: date
    bis: date
    reservationsnummer: str | None
    gesamtbetrag: str
    anzahlung: str
    restbetrag: str
    zahlungsart: str | None
    bezahlt_am: date | None


class PositionText(BaseModel):
    bezeichnung: str
    menge: str
    einzelpreis: str
    betrag: str
    mwstsatz_prozent: str


class RechnungDetail(RechnungsZeile):
    mwst_betrag_total: str
    positionen: list[PositionText]
    storniert_am: datetime | None


class ErstellenDaten(BaseModel):
    zahlungsart: str | None = None
    """bar | twint | karte | ueberweisung; leer = offen (Gast überweist später)."""


class BezahltDaten(BaseModel):
    zahlungsart: str
    datum: date | None = None


class Zahlungseinstellungen(BaseModel):
    karte: bool
    zahlungsarten: list[str] = []


def _geld(x) -> str:
    return str(Decimal(str(x or 0)).quantize(Decimal("0.01")))


def _zeile(db: Session, r: Rechnung) -> RechnungsZeile:
    from app.models.reservation import Reservationsanfrage
    b = r.buchung
    anfrage = db.get(Reservationsanfrage, b.reservationsanfrage_id) if b.reservationsanfrage_id else None
    return RechnungsZeile(
        id=r.id, nummer=r.nummer, datum=r.datum, status=r.status, gast_name=f"{r.kunde.vorname} {r.kunde.nachname}",
        buchung_id=b.id, von=b.von, bis=b.bis, reservationsnummer=anfrage.nummer if anfrage else None,
        gesamtbetrag=_geld(r.gesamtbetrag), anzahlung=_geld(r.anzahlung), restbetrag=_geld(r.restbetrag),
        zahlungsart=r.zahlungsart, bezahlt_am=r.bezahlt_am)


def _detail(db: Session, r: Rechnung) -> RechnungDetail:
    return RechnungDetail(
        **_zeile(db, r).model_dump(), mwst_betrag_total=_geld(r.mwst_betrag_total), storniert_am=r.storniert_am,
        positionen=[PositionText(bezeichnung=p.bezeichnung or p.artikel.bezeichnung, menge=zahl_text(p.menge),
                                 einzelpreis=_geld(p.einzelpreis), betrag=_geld(p.betrag),
                                 mwstsatz_prozent=zahl_text(p.mwstsatz_prozent))
                    for p in r.positionen])


def _rechnung(db: Session, rechnung_id: uuid.UUID) -> Rechnung:
    r = db.execute(select(Rechnung).options(selectinload(Rechnung.positionen).selectinload(Rechnungsposition.artikel))
                   .where(Rechnung.id == rechnung_id)).scalar_one_or_none()
    if not r:
        raise HTTPException(404, "Rechnung nicht gefunden")
    return r


@router.get("/einstellungen", response_model=Zahlungseinstellungen)
def zahlungseinstellungen(db: Session = Depends(get_db)):
    return Zahlungseinstellungen(karte=ra.karte_aktiv(db), zahlungsarten=ra.erlaubte_zahlungsarten(db))


@router.put("/einstellungen", response_model=Zahlungseinstellungen)
def zahlungseinstellungen_setzen(daten: Zahlungseinstellungen, db: Session = Depends(get_db)):
    ra.karte_setzen(db, daten.karte)
    return zahlungseinstellungen(db)


@router.get("/liste", response_model=list[RechnungsZeile])
def rechnungen_auflisten(status: str | None = None, jahr: int | None = None, db: Session = Depends(get_db)):
    """Rechnungen, neueste zuerst; optional nach Status (offen | bezahlt | storniert) und Jahr."""
    stmt = select(Rechnung).order_by(Rechnung.datum.desc(), Rechnung.nummer.desc())
    if status:
        stmt = stmt.where(Rechnung.status == status)
    if jahr:
        stmt = stmt.where(Rechnung.datum >= date(jahr, 1, 1), Rechnung.datum <= date(jahr, 12, 31))
    return [_zeile(db, r) for r in db.execute(stmt).scalars()]


@router.post("/aus-aufenthalt/{buchung_id}", response_model=RechnungDetail, status_code=201)
def aus_aufenthalt(buchung_id: uuid.UUID, daten: ErstellenDaten | None = None, db: Session = Depends(get_db)):
    """Rechnung bei der Abreise: Leistungen, Taxen, Anzahlung abgezogen; bar/TWINT sofort bezahlt."""
    b = db.get(Buchung, buchung_id)
    if not b:
        raise HTTPException(404, "Aufenthalt nicht gefunden")
    try:
        r = ra.erstellen(db, b, daten.zahlungsart if daten else None)
    except ra.RechnungFehler as exc:
        db.rollback()
        raise HTTPException(400, str(exc))
    return _detail(db, _rechnung(db, r.id))


@router.get("/details/{rechnung_id}", response_model=RechnungDetail)
def rechnung_detail(rechnung_id: uuid.UUID, db: Session = Depends(get_db)):
    return _detail(db, _rechnung(db, rechnung_id))


@router.post("/{rechnung_id}/bezahlt", response_model=RechnungDetail)
def als_bezahlt(rechnung_id: uuid.UUID, daten: BezahltDaten, db: Session = Depends(get_db)):
    try:
        ra.bezahlen(db, _rechnung(db, rechnung_id), daten.zahlungsart, daten.datum)
    except ra.RechnungFehler as exc:
        raise HTTPException(400, str(exc))
    return _detail(db, _rechnung(db, rechnung_id))


@router.post("/{rechnung_id}/stornieren", response_model=RechnungDetail)
def stornieren(rechnung_id: uuid.UUID, db: Session = Depends(get_db)):
    try:
        ra.stornieren(db, _rechnung(db, rechnung_id))
    except ra.RechnungFehler as exc:
        raise HTTPException(400, str(exc))
    return _detail(db, _rechnung(db, rechnung_id))


def _pdf_daten(db: Session, r: Rechnung) -> RechnungsDaten:
    from app.models.reservation import Reservationsanfrage
    betrieb = am.betriebsangaben(db)
    g, b = r.kunde, r.buchung
    anfrage = db.get(Reservationsanfrage, b.reservationsanfrage_id) if b.reservationsanfrage_id else None
    kunde = [f"{g.vorname} {g.nachname}", g.strasse or "", " ".join(x for x in (g.plz, g.ort) if x), g.land if g.land and g.land != "CH" else ""]
    if r.status == "bezahlt":
        art = ra.ZAHLUNGSARTEN.get(r.zahlungsart or "", "")
        vermerk = (f"Bezahlt am {r.bezahlt_am.strftime('%d.%m.%Y')}" + (f", {art}" if art else " (mit der Anzahlung)") + ". Vielen Dank!"
                   if r.bezahlt_am else "Bezahlt. Vielen Dank!")
    elif r.status == "offen":
        teile = ["Bitte überweisen Sie den Restbetrag innert 30 Tagen" + (f" mit dem Vermerk «Rechnung {r.nummer}»." if r.nummer else ".")]
        if betrieb.get("iban"):
            teile.append("IBAN " + betrieb["iban"] + (f", BIC {betrieb['bic']}" if betrieb.get("bic") else "")
                         + (f", {betrieb['kontoinhaber']}" if betrieb.get("kontoinhaber") else ""))
        vermerk = "\n".join(teile)
    else:
        vermerk = "Diese Rechnung wurde storniert."
    return RechnungsDaten(
        nummer=r.nummer, datum=r.datum.strftime("%d.%m.%Y"), kunde_zeilen=[z for z in kunde if z],
        leistungszeitraum=f"{b.von.strftime('%d.%m.%Y')} – {b.bis.strftime('%d.%m.%Y')} ({(b.bis - b.von).days} Nächte)",
        absender_zeilen=[z for z in (betrieb.get("rechnung_absender") or "").split("\n") if z.strip()],
        mwst_nummer=betrieb.get("mwst_nummer", ""), reservation=anfrage.nummer if anfrage else "",
        positionen=[RechnungsPositionZeile(bezeichnung=p.bezeichnung or p.artikel.bezeichnung, menge=Decimal(str(p.menge)),
                                           einzelpreis=Decimal(str(p.einzelpreis)), betrag=Decimal(str(p.betrag)),
                                           mwstsatz_prozent=Decimal(str(p.mwstsatz_prozent))) for p in r.positionen],
        gesamtbetrag=Decimal(str(r.gesamtbetrag)), anzahlung=Decimal(str(r.anzahlung or 0)),
        zahlungsvermerk=vermerk, storniert=r.status == "storniert", logo=(logo.lesen(db) or (None,))[0])


@router.get("/{rechnung_id}/pdf")
def rechnung_als_pdf(rechnung_id: uuid.UUID, db: Session = Depends(get_db)):
    r = _rechnung(db, rechnung_id)
    return Response(rechnung_pdf(_pdf_daten(db, r)), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="Rechnung-{r.nummer}.pdf"'})


@router.get("/{rechnung_id}", response_model=RechnungOut)
def rechnung_lesen(rechnung_id: uuid.UUID, db: Session = Depends(get_db)):
    rechnung = db.execute(
        select(Rechnung)
        .options(selectinload(Rechnung.positionen))
        .where(Rechnung.id == rechnung_id)
    ).scalar_one_or_none()
    if not rechnung:
        raise HTTPException(404, "Rechnung nicht gefunden")
    return rechnung
