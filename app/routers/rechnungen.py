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
from datetime import date
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models.artikel import Artikel, ArtikelPreis, Saison
from app.models.buchung import Buchung
from app.models.rechnung import Rechnung, Rechnungsposition
from app.schemas.rechnung import RechnungOut, RechnungspositionCreate
from app.services.mwst import mwst_betrag_aus_brutto
from app.services.pdf_rechnung import (
    RechnungsDaten,
    RechnungsPositionZeile,
    erzeuge_rechnung_pdf,
)
from app.services.rechnungsnummer import naechste_rechnungsnummer
from app.services.taxen import berechne_taxen_fuer_buchung

router = APIRouter(prefix="/rechnungen", tags=["Rechnungen"])

# Ablageort für generierte Rechnungs-PDFs. In Produktion durch die
# Infrastruktur-Fachpersonen an einen dauerhaften Speicherort (z.B.
# Objektspeicher) anzubinden – hier bewusst simpel gehalten.
PDF_VERZEICHNIS = Path("./generierte_dokumente/rechnungen")


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

    return Decimal(str(preis_row.preis)), Decimal(str(artikel.mwstsatz.satz_prozent))


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


@router.post("/{rechnung_id}/pdf-erzeugen")
def pdf_erzeugen(rechnung_id: uuid.UUID, db: Session = Depends(get_db)):
    """Rendert die Rechnung als PDF (Konzept Abschnitt 12.1) und speichert den Pfad."""
    rechnung = db.execute(
        select(Rechnung)
        .options(
            selectinload(Rechnung.positionen).selectinload(Rechnungsposition.artikel),
            selectinload(Rechnung.kunde),
        )
        .where(Rechnung.id == rechnung_id)
    ).scalar_one_or_none()
    if not rechnung:
        raise HTTPException(404, "Rechnung nicht gefunden")

    daten = RechnungsDaten(
        nummer=rechnung.nummer,
        datum=rechnung.datum.strftime("%d.%m.%Y"),
        kunde_name=f"{rechnung.kunde.vorname} {rechnung.kunde.nachname}",
        kunde_adresse=f"{rechnung.kunde.plz or ''} {rechnung.kunde.ort or ''}".strip(),
        leistungszeitraum="",  # TODO: aus verknüpften Aufenthalten ableiten
        betrieb_name="Camping Aeschi",  # TODO: aus Campingplatz-Stammdaten laden
        betrieb_adresse="",
        betrieb_mwst_nummer="TODO",
        positionen=[
            RechnungsPositionZeile(
                bezeichnung=p.artikel.bezeichnung,
                menge=Decimal(str(p.menge)),
                einzelpreis=Decimal(str(p.einzelpreis)),
                betrag=Decimal(str(p.betrag)),
                mwstsatz_prozent=Decimal(str(p.mwstsatz_prozent)),
            )
            for p in rechnung.positionen
        ],
        gesamtbetrag=Decimal(str(rechnung.gesamtbetrag)),
    )

    PDF_VERZEICHNIS.mkdir(parents=True, exist_ok=True)
    ziel_pfad = PDF_VERZEICHNIS / f"{rechnung.nummer}.pdf"
    erzeuge_rechnung_pdf(daten, str(ziel_pfad))

    rechnung.pdf_pfad = str(ziel_pfad)
    db.commit()
    return {"pdf_pfad": str(ziel_pfad)}
