"""Modelle: Campingplatz (Betriebsstammdaten) und Stellplatz."""
import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import GUID, IDMixin, TimestampMixin


class Campingplatz(Base, IDMixin, TimestampMixin):
    """Stammdaten des Betriebs (aktuell: ein Datensatz pro Installation)."""
    __tablename__ = "campingplatz"

    name: Mapped[str] = mapped_column(String(200))
    adresse: Mapped[str | None] = mapped_column(String(300))
    gemeinde: Mapped[str | None] = mapped_column(String(100))
    kanton: Mapped[str | None] = mapped_column(String(50))
    gemeinde_nummer: Mapped[str | None] = mapped_column(String(20))
    """BFS-Gemeindenummer, u.a. für Feratel- und HESTA-Meldung relevant."""

    stellplaetze: Mapped[list["Stellplatz"]] = relationship(back_populates="campingplatz")


class Stellplatz(Base, IDMixin, TimestampMixin):
    """Physische, buchbare Einheit (Zeltwiese, Wohnwagen, Zwärgli, Spycher …)."""
    __tablename__ = "stellplatz"

    campingplatz_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("campingplatz.id"))
    bezeichnung: Mapped[str] = mapped_column(String(100))
    typ: Mapped[str] = mapped_column(String(50))
    """z.B. zeltwiese, wohnwagen, camper, zwaergli, spycher"""
    max_personen: Mapped[int | None] = mapped_column(Integer)
    strom_anschluss: Mapped[bool] = mapped_column(default=False)
    artikel_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("artikel.id"))
    """Verweis auf den Standard-Artikel für die saisonale Preisfindung."""

    campingplatz: Mapped["Campingplatz"] = relationship(back_populates="stellplaetze")
    buchungen: Mapped[list["Buchung"]] = relationship(back_populates="stellplatz")
