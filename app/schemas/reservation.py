import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ReservationsanfrageCreate(BaseModel):
    """
    Eingabe beim Erfassen einer Anfrage (E-Mail-Kanal: durch eine Person
    aus dem Mailinhalt übertragen; Homepage-Kanal: automatisch befüllt).
    """
    quelle: str = Field(pattern="^(email|homepage_formular|manuell)$")
    eingangs_datum: datetime
    sprache: str = "de"
    gast_name: str
    gast_email: EmailStr
    gast_telefon: str | None = None
    gewuenscht_von: date
    gewuenscht_bis: date
    stellplatz_typ: str | None = None
    anzahl_erwachsene: int = 1
    anzahl_kinder: int = 0
    bemerkung: str | None = None
    rohtext: str | None = None
    newsletter_einwilligung: bool = False


class ReservationsanfrageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    quelle: str
    eingangs_datum: datetime
    sprache: str
    gast_name: str
    gast_email: str
    gewuenscht_von: date
    gewuenscht_bis: date
    stellplatz_typ: str | None
    anzahl_erwachsene: int
    anzahl_kinder: int
    vollstaendig: bool
    fehlende_angaben: str | None
    status: str
    newsletter_einwilligung: bool
