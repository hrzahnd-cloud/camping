"""
Modul «Artikel & Preise»: Saisons je Jahr und Preise zentral pflegen.

Saisonale Artikel haben je Saison (Vor-, Haupt-, Nachsaison) einen Preis,
ganzjährige einen einzigen, der für alle Jahre gilt. Ein neues Jahr übernimmt
Saisons und Preise des Vorjahres. Bestehende Rechnungen sind davon nicht
betroffen (Preise und MWST werden dort als Kopie gespeichert).
"""
import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models.artikel import Artikel, ArtikelPreis
from app.services import preise as pr
from app.services.mwst import prozent_fuer_artikel

router = APIRouter(prefix="/preise", tags=["Artikel & Preise"])

REIHENFOLGE = ["ERWACHSENE", "KINDER", "KLEINKINDER", "ZELT", "WOHNWAGEN", "CAMPER", "ZWAERGLI", "SPYCHER",
               "STROM", "UMWELTABGABE", "AUTO", "MOTORRAD", "WASSERTANK"]
EINHEIT = {"pro_person_nacht": "pro Person und Nacht", "pro_nacht": "pro Nacht", "pro_tag": "pro Tag", "stueck": "pro Stück"}


class SaisonDaten(BaseModel):
    id: uuid.UUID | None = None
    typ: str
    bezeichnung: str | None = None
    gueltig_ab: date
    gueltig_bis: date


class ArtikelZeile(BaseModel):
    id: uuid.UUID
    code: str
    bezeichnung: str
    einheit: str
    saisonal: bool
    mwst_prozent: float | None
    preise: dict[str, float | None]
    """Saisonal: typ -> Preis; ganzjährig: {"ganzjaehrig": Preis}."""


class Preisliste(BaseModel):
    jahr: int
    jahre: list[int]
    saisons: list[SaisonDaten]
    artikel: list[ArtikelZeile]


class PreisEingabe(BaseModel):
    artikel_id: uuid.UUID
    saison: str
    """vorsaison | hauptsaison | nachsaison | ganzjaehrig"""
    preis: Decimal = Field(ge=0, le=10000, decimal_places=2)


class PreislisteSpeichern(BaseModel):
    saisons: list[SaisonDaten] = []
    preise: list[PreisEingabe] = []


def _liste(db: Session, jahr: int) -> Preisliste:
    saisons = pr.saisons_im_jahr(db, jahr)
    nach_typ = {s.typ: s for s in saisons}
    artikel = list(db.execute(select(Artikel).where(Artikel.aktiv.is_(True), Artikel.kategorie != "taxe")
                              .options(selectinload(Artikel.preise), selectinload(Artikel.mwstsatz))).scalars())
    artikel.sort(key=lambda a: (REIHENFOLGE.index(a.code) if a.code in REIHENFOLGE else 99, a.bezeichnung))
    stichtag = saisons[0].gueltig_ab if saisons else date(jahr, 7, 1)
    zeilen = []
    for a in artikel:
        saisonal = pr.ist_saisonal(a)
        if saisonal:
            preise = {typ: next((float(p.preis) for p in a.preise if s and p.saison_id == s.id), None)
                      for typ, s in ((t, nach_typ.get(t)) for t in pr.SAISON_DATEN)}
        else:
            preise = {"ganzjaehrig": next((float(p.preis) for p in a.preise if p.saison_id is None), None)}
        try:
            mwst = float(prozent_fuer_artikel(db, a, stichtag))
        except ValueError:
            mwst = None
        zeilen.append(ArtikelZeile(id=a.id, code=a.code, bezeichnung=a.bezeichnung, einheit=EINHEIT.get(a.einheit, a.einheit),
                                   saisonal=saisonal, mwst_prozent=mwst, preise=preise))
    return Preisliste(jahr=jahr, jahre=pr.jahre(db),
                      saisons=[SaisonDaten(id=s.id, typ=s.typ or "", bezeichnung=s.bezeichnung,
                                           gueltig_ab=s.gueltig_ab, gueltig_bis=s.gueltig_bis) for s in saisons],
                      artikel=zeilen)


@router.get("/jahre", response_model=list[int])
def jahre_auflisten(db: Session = Depends(get_db)):
    return pr.jahre(db)


@router.get("/{jahr}", response_model=Preisliste)
def preisliste(jahr: int, db: Session = Depends(get_db)):
    return _liste(db, jahr)


@router.put("/{jahr}", response_model=Preisliste)
def preisliste_speichern(jahr: int, daten: PreislisteSpeichern, db: Session = Depends(get_db)):
    """Saisondaten des Jahres und Preise ändern (nur die mitgeschickten)."""
    saisons = {s.typ: s for s in pr.saisons_im_jahr(db, jahr)}
    neu = {s.typ: (s.gueltig_ab, s.gueltig_bis) for s in saisons.values()}
    for e in daten.saisons:
        if e.typ not in saisons:
            raise HTTPException(400, f"Saison «{e.typ}» gibt es {jahr} nicht")
        if e.gueltig_ab.year != jahr or e.gueltig_bis.year != jahr or e.gueltig_bis < e.gueltig_ab:
            raise HTTPException(400, f"{pr.SAISON_NAMEN.get(e.typ, e.typ)}: Daten müssen im Jahr {jahr} liegen, «bis» nach «von»")
        neu[e.typ] = (e.gueltig_ab, e.gueltig_bis)
    reihe = sorted(neu.items(), key=lambda x: x[1][0])
    for (t1, (_, b1)), (t2, (a2, _)) in zip(reihe, reihe[1:]):
        if a2 <= b1:
            raise HTTPException(400, f"{pr.SAISON_NAMEN.get(t1, t1)} und {pr.SAISON_NAMEN.get(t2, t2)} überschneiden sich")
    for typ, (ab, bis) in neu.items():
        saisons[typ].gueltig_ab, saisons[typ].gueltig_bis = ab, bis

    for e in daten.preise:
        artikel = db.get(Artikel, e.artikel_id)
        if artikel is None:
            raise HTTPException(404, "Artikel nicht gefunden")
        if e.saison == "ganzjaehrig":
            saison_id = None
        elif e.saison in saisons:
            saison_id = saisons[e.saison].id
        else:
            raise HTTPException(400, f"Saison «{e.saison}» gibt es {jahr} nicht")
        zeile = db.execute(select(ArtikelPreis).where(ArtikelPreis.artikel_id == artikel.id,
                                                      ArtikelPreis.saison_id.is_(None) if saison_id is None
                                                      else ArtikelPreis.saison_id == saison_id)).scalar_one_or_none()
        if zeile is None:
            db.add(ArtikelPreis(artikel_id=artikel.id, saison_id=saison_id, preis=e.preis))
        else:
            zeile.preis = e.preis
    db.commit()
    return _liste(db, jahr)


class Uebernahme(BaseModel):
    von_jahr: int


@router.post("/{jahr}/uebernehmen", response_model=Preisliste, status_code=201)
def jahr_uebernehmen(jahr: int, daten: Uebernahme, db: Session = Depends(get_db)):
    """Saisons und Preise eines Vorjahres für ein neues Jahr übernehmen."""
    if not 2000 <= jahr <= 2100:
        raise HTTPException(400, "Ungültiges Jahr")
    try:
        pr.jahr_uebernehmen(db, jahr, daten.von_jahr)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return _liste(db, jahr)

