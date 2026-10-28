"""
Modell: Modul-Schalter für die Bedienoberfläche.

Welche Bereiche im Menü erscheinen, wird hier gespeichert. Ausgeschaltete
Module bleiben vollständig gebaut (Datenbank, API), werden in der
Oberfläche aber nicht angezeigt. Fehlt ein Eintrag, gilt der Standard aus
app/services/module.py.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.common import _utcnow


class ModulEinstellung(Base):
    __tablename__ = "modul_einstellung"

    code: Mapped[str] = mapped_column(String(50), primary_key=True)
    aktiv: Mapped[bool] = mapped_column(Boolean, default=False)
    geaendert_am: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class AppEinstellung(Base):
    """
    Einzelne Einstellung als Schlüssel/Wert, z.B. Signatur, IBAN, TWINT.
    Werte werden in der Oberfläche unter "Einstellungen" gepflegt und nicht im
    Code abgelegt (das Repository ist öffentlich).
    """
    __tablename__ = "app_einstellung"

    schluessel: Mapped[str] = mapped_column(String(60), primary_key=True)
    wert: Mapped[str] = mapped_column(Text, default="")
    geaendert_am: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
