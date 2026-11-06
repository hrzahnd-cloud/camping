"""Modelle: Gast, Buchung, Aufenthalt."""
import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import GUID, IDMixin, TimestampMixin


class Gast(Base, IDMixin, TimestampMixin):
    """Einzelperson – Hauptbucher oder Mitreisende(r)."""
    __tablename__ = "gast"

    vorname: Mapped[str] = mapped_column(String(100))
    nachname: Mapped[str] = mapped_column(String(100))
    geburtsdatum: Mapped[date | None] = mapped_column(Date)
    nationalitaet: Mapped[str | None] = mapped_column(String(2))
    """ISO-3166-1 alpha-2 Ländercode, zentrale Dimension für Feratel & HESTA."""
    strasse: Mapped[str | None] = mapped_column(String(200))
    """Pflichtfeld des Feratel-Meldescheins (Hauptgast)."""
    plz: Mapped[str | None] = mapped_column(String(20))
    ort: Mapped[str | None] = mapped_column(String(100))
    land: Mapped[str | None] = mapped_column(String(2))
    email: Mapped[str | None] = mapped_column(String(255))
    telefon: Mapped[str | None] = mapped_column(String(50))

    aufenthalte: Mapped[list["Aufenthalt"]] = relationship(back_populates="gast")


class Buchung(Base, IDMixin, TimestampMixin):
    """
    Aufenthalt auf dem Platz über einen Zeitraum. Entsteht beim Check-in am
    Anreisetag – aus einer akzeptierten Reservation oder ohne Reservation
    (z.B. Nebensaison). Die Zuteilung einzelner Stellplätze erfolgt ausserhalb
    des Tools; `stellplatz_id` ist deshalb optional, massgebend für die
    Belegung ist `stellplatz_typ` (optional mit Platznummer als Freitext).
    """
    __tablename__ = "buchung"

    stellplatz_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("stellplatz.id"))
    stellplatz_typ: Mapped[str | None] = mapped_column(String(50))
    """zeltwiese | wohnwagen | camper | zwaergli | spycher (wie Reservationsanfrage)"""
    platz: Mapped[str | None] = mapped_column(String(50))
    """Platznummer/-bezeichnung als Freitext, optional."""
    anzahl_erwachsene: Mapped[int] = mapped_column(Integer, default=1)
    anzahl_kinder: Mapped[int] = mapped_column(Integer, default=0)
    bemerkung: Mapped[str | None] = mapped_column(Text)
    von: Mapped[date] = mapped_column(Date)
    bis: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), default="angefragt")
    """angefragt | bestaetigt | eingecheckt | ausgecheckt | storniert"""
    hauptgast_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("gast.id"))
    reservationsanfrage_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("reservationsanfrage.id")
    )
    """Herkunft, falls aus einer Reservationsanfrage entstanden (Konzept Abschnitt 10)."""

    stellplatz: Mapped["Stellplatz | None"] = relationship(back_populates="buchungen")
    hauptgast: Mapped["Gast"] = relationship(foreign_keys=[hauptgast_id])
    aufenthalte: Mapped[list["Aufenthalt"]] = relationship(back_populates="buchung")
    rechnung: Mapped["Rechnung | None"] = relationship(back_populates="buchung", uselist=False)


class Aufenthalt(Base, IDMixin, TimestampMixin):
    """Verknüpfung Gast ↔ Buchung mit effektiven An-/Abreisedaten."""
    __tablename__ = "aufenthalt"

    buchung_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("buchung.id"))
    gast_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("gast.id"))
    ankunft: Mapped[date] = mapped_column(Date)
    abreise: Mapped[date] = mapped_column(Date)
    taxpflichtig: Mapped[bool] = mapped_column(default=True)
    """False z.B. bei steuerrechtlichem Wohnsitz in der Gemeinde."""

    buchung: Mapped["Buchung"] = relationship(back_populates="aufenthalte")
    gast: Mapped["Gast"] = relationship(back_populates="aufenthalte")

    @property
    def anzahl_naechte(self) -> int:
        return (self.abreise - self.ankunft).days
