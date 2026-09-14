import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr


class GastCreate(BaseModel):
    vorname: str
    nachname: str
    geburtsdatum: date | None = None
    nationalitaet: str | None = None
    plz: str | None = None
    ort: str | None = None
    land: str | None = None
    email: EmailStr | None = None
    telefon: str | None = None


class GastOut(GastCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID


class BuchungCreate(BaseModel):
    stellplatz_id: uuid.UUID
    von: date
    bis: date
    hauptgast_id: uuid.UUID
    reservationsanfrage_id: uuid.UUID | None = None


class BuchungOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    stellplatz_id: uuid.UUID
    von: date
    bis: date
    status: str
    hauptgast_id: uuid.UUID


class AufenthaltCreate(BaseModel):
    buchung_id: uuid.UUID
    gast_id: uuid.UUID
    ankunft: date
    abreise: date
    taxpflichtig: bool = True


class AufenthaltOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    buchung_id: uuid.UUID
    gast_id: uuid.UUID
    ankunft: date
    abreise: date
    taxpflichtig: bool
