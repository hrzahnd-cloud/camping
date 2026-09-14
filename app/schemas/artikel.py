import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict


class MwstsatzOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    bezeichnung: str
    satz_prozent: float
    gueltig_ab: date
    gueltig_bis: date | None


class SaisonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    bezeichnung: str
    gueltig_ab: date
    gueltig_bis: date


class ArtikelPreisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    saison_id: uuid.UUID | None
    preis: float


class ArtikelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    bezeichnung: str
    kategorie: str
    einheit: str
    aktiv: bool
    mwstsatz: MwstsatzOut
    preise: list[ArtikelPreisOut] = []
