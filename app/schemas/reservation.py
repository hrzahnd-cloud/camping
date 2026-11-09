import uuid
from datetime import date, datetime
from decimal import Decimal

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

StellplatzTyp = Literal["zeltwiese", "wohnwagen", "camper", "zwaergli", "spycher"]
"""Codes wie beim Mail-Import (app/services/mail_import.py)."""

AnfrageStatus = Literal[
    "neu", "unvollstaendig", "geprueft_vollstaendig", "erstantwort_gesendet",
    "zahlung_ausstehend", "bezahlt_akzeptiert", "abgelehnt", "storniert", "in_abklaerung",
    "angereist", "nicht_erschienen",
]


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
    gewuenscht_von: date | None = None
    gewuenscht_bis: date | None = None
    """Darf fehlen (z.B. telefonische Anfrage); die Anfrage gilt dann als unvollständig."""
    stellplatz_typ: StellplatzTyp | None = None
    anzahl_erwachsene: int = Field(default=1, ge=0)
    anzahl_kinder: int = Field(default=0, ge=0)
    anzahl_kleinkinder: int = Field(default=0, ge=0)
    bemerkung: str | None = None
    rohtext: str | None = None
    newsletter_einwilligung: bool = False


class ReservationsanfrageUpdate(BaseModel):
    """Teilweise Änderung einer Anfrage, z.B. fehlende Angaben nachtragen."""
    sprache: str | None = None
    gast_name: str | None = None
    gast_email: EmailStr | None = None
    gast_telefon: str | None = None
    gewuenscht_von: date | None = None
    gewuenscht_bis: date | None = None
    stellplatz_typ: StellplatzTyp | None = None
    anzahl_erwachsene: int | None = Field(default=None, ge=0)
    anzahl_kinder: int | None = Field(default=None, ge=0)
    anzahl_kleinkinder: int | None = Field(default=None, ge=0)
    bemerkung: str | None = None
    newsletter_einwilligung: bool | None = None


class StatusAenderung(BaseModel):
    status: AnfrageStatus


class ReservationsanfrageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    nummer: str | None = None
    quelle: str
    eingangs_datum: datetime
    sprache: str
    gast_name: str
    gast_email: str
    gast_telefon: str | None = None
    gewuenscht_von: date | None
    gewuenscht_bis: date | None
    stellplatz_typ: str | None
    anzahl_erwachsene: int
    anzahl_kinder: int
    anzahl_kleinkinder: int = 0
    bemerkung: str | None = None
    vollstaendig: bool
    fehlende_angaben: str | None
    status: str
    newsletter_einwilligung: bool
    neue_mails: int = 0
    """Ungelesene Mails des Gastes zu dieser Anfrage (aus dem Postfach)."""


class ReservationsanfrageDetail(ReservationsanfrageOut):
    """Mit Originaltext der Mail (nur in der Detailansicht, nicht in Listen)."""
    rohtext: str | None = None
    anzahlung_verlangt: Decimal | None = None
    anzahlung_erhalten: Decimal | None = None
    """Summe der gutgeschriebenen Anzahlungen in CHF (Grundlage für die Rechnung)."""
    anzahlung_eingegangen_am: date | None = None
    anzahlung_zahlungsart: str | None = None
    hohe_belegung: list[dict] = []
    """Nächte, in denen mit dieser Anfrage die Meldegrenze (z.B. 45 von 50) erreicht wird."""
    buchung_id: uuid.UUID | None = None
    """Aufenthalt, falls angereist."""
