import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class RechnungspositionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    artikel_id: uuid.UUID
    menge: float
    einzelpreis: float
    betrag: float
    mwstsatz_prozent: float
    mwst_betrag: float


class RechnungOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    buchung_id: uuid.UUID
    kunde_id: uuid.UUID
    nummer: str
    datum: date
    status: str
    gesamtbetrag: float
    mwst_betrag_total: float
    pdf_pfad: str | None
    versendet_am: datetime | None
    positionen: list[RechnungspositionOut] = []


class RechnungspositionCreate(BaseModel):
    """Manuell hinzugefügte Zusatzposition (z.B. Strom, Wassertankfüllung)."""
    artikel_id: uuid.UUID
    menge: float = 1
