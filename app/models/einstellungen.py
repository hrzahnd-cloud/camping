"""
Modell: Modul-Schalter für die Bedienoberfläche.

Welche Bereiche im Menü erscheinen, wird hier gespeichert. Ausgeschaltete
Module bleiben vollständig gebaut (Datenbank, API), werden in der
Oberfläche aber nicht angezeigt. Fehlt ein Eintrag, gilt der Standard aus
app/services/module.py.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
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
