"""Artikel-Katalog inkl. saisonaler Preisfindung (Konzeptdokument Abschnitt 9)."""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models.artikel import Artikel, ArtikelPreis, Saison
from app.schemas.artikel import ArtikelOut

router = APIRouter(prefix="/artikel", tags=["Artikel & Preise"])


@router.get("", response_model=list[ArtikelOut])
def artikel_auflisten(nur_aktive: bool = True, db: Session = Depends(get_db)):
    stmt = select(Artikel).options(
        selectinload(Artikel.mwstsatz), selectinload(Artikel.preise)
    )
    if nur_aktive:
        stmt = stmt.where(Artikel.aktiv.is_(True))
    return db.execute(stmt).scalars().all()


@router.get("/{artikel_id}/preis")
def preis_ermitteln(artikel_id: uuid.UUID, stichtag: date, db: Session = Depends(get_db)):
    """
    Ermittelt den gültigen Preis eines Artikels für ein bestimmtes Datum:
    zuerst wird die passende Saison gesucht, dann der zugehörige
    ArtikelPreis. Existiert kein saisonspezifischer Preis, wird der
    saisonunabhängige Preis (saison_id IS NULL) verwendet.
    """
    artikel = db.get(Artikel, artikel_id)
    if not artikel:
        raise HTTPException(404, "Artikel nicht gefunden")

    saison = db.execute(
        select(Saison).where(Saison.gueltig_ab <= stichtag, Saison.gueltig_bis >= stichtag)
    ).scalars().first()

    preis = None
    if saison:
        preis = db.execute(
            select(ArtikelPreis).where(
                ArtikelPreis.artikel_id == artikel_id, ArtikelPreis.saison_id == saison.id
            )
        ).scalar_one_or_none()

    if preis is None:
        preis = db.execute(
            select(ArtikelPreis).where(
                ArtikelPreis.artikel_id == artikel_id, ArtikelPreis.saison_id.is_(None)
            )
        ).scalar_one_or_none()

    if preis is None:
        raise HTTPException(404, f"Kein gültiger Preis für Artikel am {stichtag} gefunden")

    return {
        "artikel_id": str(artikel_id),
        "stichtag": stichtag.isoformat(),
        "saison": saison.bezeichnung if saison else None,
        "preis": float(preis.preis),
        "mwstsatz_prozent": float(artikel.mwstsatz.satz_prozent),
    }
