"""
HESTA-Monatsmeldung (Konzept Abschnitt 6): Vorschau, PDF/CSV-Export,
Meldeprotokoll und E-Mail-Versand an das BFS.

Der E-Mail-Versand ist bewusst doppelt gesichert: er läuft nur, wenn
HESTA_EMAIL_VERSAND_AKTIV=true gesetzt ist, SMTP konfiguriert ist und die
BUR-Nummer vorliegt. Der Standard ist "aus", bis das BFS das Format bestätigt hat.
"""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.models.campingplatz import Campingplatz
from app.models.meldungen import HestaMeldung, HestaMeldungPosition
from app.services.hesta import HestaPosition, aggregiere_hesta_monat
from app.services.hesta_export import (
    HestaBericht,
    bericht_als_dict,
    erzeuge_hesta_csv,
    erzeuge_hesta_mail,
    erzeuge_hesta_pdf,
    schliessungstage_aus_text,
    schliessungstage_zu_text,
)
from app.services.mailversand import MailNichtKonfiguriert, sende_mail, smtp_konfiguriert

router = APIRouter(prefix="/hesta", tags=["HESTA"])


class MeldungEingabe(BaseModel):
    jahr: int = Field(ge=2000, le=2100)
    monat: int = Field(ge=1, le=12)
    schliessungstage: list[tuple[date, date]] = []
    belegte_zimmer: int | None = Field(default=None, ge=0)
    durchschnittsertrag_pro_logiernacht: Decimal | None = Field(default=None, ge=0)
    bemerkung: str | None = None


def _bericht(db: Session, jahr: int, monat: int, meldung: HestaMeldung | None = None) -> HestaBericht:
    betrieb = db.execute(select(Campingplatz)).scalars().first()
    if meldung is not None:
        positionen = [
            HestaPosition(p.land, p.anzahl_personen, p.anzahl_uebernachtungen)
            for p in sorted(meldung.positionen, key=lambda p: p.land)
        ]
    else:
        positionen = aggregiere_hesta_monat(db, jahr, monat)
    return HestaBericht(
        betrieb_name=betrieb.name if betrieb else "Campingplatz",
        jahr=jahr,
        monat=monat,
        positionen=positionen,
        adresse=(betrieb.adresse or "") if betrieb else "",
        gemeinde=(betrieb.gemeinde or "") if betrieb else "",
        bur_nummer=betrieb.bur_nummer if betrieb else None,
        anzahl_zimmer=betrieb.hesta_anzahl_zimmer if betrieb else None,
        anzahl_betten=betrieb.hesta_anzahl_betten if betrieb else None,
        schliessungstage=schliessungstage_aus_text(meldung.schliessungstage) if meldung else [],
        belegte_zimmer=meldung.belegte_zimmer if meldung else None,
        durchschnittsertrag=(
            Decimal(str(meldung.durchschnittsertrag_pro_logiernacht))
            if meldung and meldung.durchschnittsertrag_pro_logiernacht is not None else None
        ),
        bemerkung=(meldung.bemerkung or "") if meldung else "",
    )


def _meldung_zu_dict(m: HestaMeldung) -> dict:
    return {
        "id": str(m.id), "jahr": m.jahr, "monat": m.monat, "status": m.status,
        "generiert_am": m.generiert_am, "eingereicht_am": m.eingereicht_am,
        "versandart": m.versandart,
        "total_personen": sum(p.anzahl_personen for p in m.positionen),
        "total_uebernachtungen": sum(p.anzahl_uebernachtungen for p in m.positionen),
    }


def _hole_meldung(db: Session, meldung_id: uuid.UUID) -> HestaMeldung:
    meldung = db.get(HestaMeldung, meldung_id)
    if not meldung:
        raise HTTPException(404, "HESTA-Meldung nicht gefunden")
    return meldung


@router.get("/vorschau")
def vorschau(
    jahr: int = Query(ge=2000, le=2100), monat: int = Query(ge=1, le=12), db: Session = Depends(get_db)
):
    """Aggregierte Zahlen des Monats aus den bezahlten Rechnungen, inkl. offener Punkte."""
    return bericht_als_dict(_bericht(db, jahr, monat))


@router.get("/pdf")
def vorschau_pdf(
    jahr: int = Query(ge=2000, le=2100), monat: int = Query(ge=1, le=12), db: Session = Depends(get_db)
):
    pdf = erzeuge_hesta_pdf(_bericht(db, jahr, monat))
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="hesta_{jahr}-{monat:02d}.pdf"'})


@router.get("/csv")
def vorschau_csv(
    jahr: int = Query(ge=2000, le=2100), monat: int = Query(ge=1, le=12), db: Session = Depends(get_db)
):
    return Response(erzeuge_hesta_csv(_bericht(db, jahr, monat)), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="hesta_{jahr}-{monat:02d}.csv"'})


@router.post("/meldungen", status_code=201)
def meldung_erzeugen(daten: MeldungEingabe, db: Session = Depends(get_db)):
    """Friert die Monatszahlen als Meldung ein (Status 'entwurf'); eine bereits eingereichte Meldung bleibt unverändert."""
    meldung = db.execute(
        select(HestaMeldung).where(HestaMeldung.jahr == daten.jahr, HestaMeldung.monat == daten.monat)
    ).scalars().first()
    if meldung and meldung.status == "eingereicht":
        raise HTTPException(409, "Für diesen Monat wurde bereits eine Meldung eingereicht")
    if meldung is None:
        meldung = HestaMeldung(jahr=daten.jahr, monat=daten.monat)
        db.add(meldung)

    meldung.positionen.clear()
    for p in aggregiere_hesta_monat(db, daten.jahr, daten.monat):
        meldung.positionen.append(HestaMeldungPosition(
            land=p.land, anzahl_personen=p.anzahl_personen, anzahl_uebernachtungen=p.anzahl_uebernachtungen,
        ))
    meldung.schliessungstage = schliessungstage_zu_text(daten.schliessungstage) or None
    meldung.belegte_zimmer = daten.belegte_zimmer
    meldung.durchschnittsertrag_pro_logiernacht = daten.durchschnittsertrag_pro_logiernacht
    meldung.bemerkung = daten.bemerkung
    meldung.generiert_am = datetime.now(timezone.utc)
    meldung.status = "entwurf"
    db.commit()
    db.refresh(meldung)
    return _meldung_zu_dict(meldung)


@router.get("/meldungen")
def meldungen_auflisten(db: Session = Depends(get_db)):
    meldungen = db.execute(
        select(HestaMeldung).order_by(HestaMeldung.jahr.desc(), HestaMeldung.monat.desc())
    ).scalars().all()
    return [_meldung_zu_dict(m) for m in meldungen]


@router.get("/meldungen/{meldung_id}/pdf")
def meldung_pdf(meldung_id: uuid.UUID, db: Session = Depends(get_db)):
    meldung = _hole_meldung(db, meldung_id)
    pdf = erzeuge_hesta_pdf(_bericht(db, meldung.jahr, meldung.monat, meldung))
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="hesta_{meldung.jahr}-{meldung.monat:02d}.pdf"'})


@router.post("/meldungen/{meldung_id}/als-eingereicht-markieren")
def als_eingereicht_markieren(meldung_id: uuid.UUID, db: Session = Depends(get_db)):
    """Für den manuellen Weg: PDF wurde ausgedruckt/selbst beim BFS erfasst."""
    meldung = _hole_meldung(db, meldung_id)
    meldung.status = "eingereicht"
    meldung.versandart = "manuell_pdf"
    meldung.eingereicht_am = datetime.now(timezone.utc)
    db.commit()
    return _meldung_zu_dict(meldung)


@router.post("/meldungen/{meldung_id}/versenden")
def meldung_per_mail_versenden(
    meldung_id: uuid.UUID, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
):
    meldung = _hole_meldung(db, meldung_id)
    if not settings.hesta_email_versand_aktiv:
        raise HTTPException(409, "E-Mail-Versand an das BFS ist nicht aktiviert (HESTA_EMAIL_VERSAND_AKTIV).")
    if not smtp_konfiguriert(settings):
        raise HTTPException(503, "SMTP ist nicht konfiguriert (SMTP_HOST fehlt).")

    bericht = _bericht(db, meldung.jahr, meldung.monat, meldung)
    if not bericht.bur_nummer:
        raise HTTPException(409, "BUR-Nummer fehlt: ohne sie kann das BFS die Meldung nicht zuordnen.")

    nachricht = erzeuge_hesta_mail(
        bericht, settings.smtp_absender, settings.hesta_empfaenger,
        erzeuge_hesta_pdf(bericht), erzeuge_hesta_csv(bericht),
    )
    try:
        sende_mail(settings, nachricht)
    except MailNichtKonfiguriert as exc:
        raise HTTPException(503, str(exc))
    except OSError as exc:
        raise HTTPException(502, f"Versand fehlgeschlagen: {exc}")

    meldung.status = "eingereicht"
    meldung.versandart = "email"
    meldung.eingereicht_am = datetime.now(timezone.utc)
    db.commit()
    return _meldung_zu_dict(meldung)
