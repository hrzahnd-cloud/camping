"""
Modelle: Rechnung, Rechnungsposition, Rechnungsnummernzaehler.

Siehe Konzeptdokument Abschnitt 9.4 (MWST-Berechnung) und 12 (Versand/Nummerierung).
"""
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import GUID, IDMixin, TimestampMixin


class Rechnungsnummernzaehler(Base, IDMixin, TimestampMixin):
    """
    Zähler je Jahr für lückenlose, revisionssichere Rechnungsnummern.

    Format der Rechnungsnummer: '{jahr}-{laufnummer}', z.B. '2026-1000'.
    Start bei 999, sodass die erste Rechnung des Jahres die 1000 erhält.
    Das Hochzählen MUSS atomar erfolgen (siehe app/services/rechnungsnummer.py).
    """
    __tablename__ = "rechnungsnummernzaehler"
    __table_args__ = (UniqueConstraint("jahr", name="uq_rechnungsnummernzaehler_jahr"),)

    jahr: Mapped[int] = mapped_column(Integer)
    letzte_vergebene_nummer: Mapped[int] = mapped_column(Integer, default=999)


class Rechnung(Base, IDMixin, TimestampMixin):
    """Abrechnung einer Buchung: Übernachtung, Taxen, Zusatzleistungen."""
    __tablename__ = "rechnung"

    buchung_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("buchung.id"))
    kunde_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("gast.id"))
    """Denormalisiert für einfache Auswertung 'Umsatz nach Kunde' (i.d.R. Hauptgast)."""
    nummer: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    """Format 'JJJJ-XXXX', siehe Rechnungsnummernzaehler."""
    datum: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="offen")
    """offen | bezahlt"""
    gesamtbetrag: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    mwst_betrag_total: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    pdf_pfad: Mapped[str | None] = mapped_column(String(500))
    versendet_am: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    buchung: Mapped["Buchung"] = relationship(back_populates="rechnung")
    kunde: Mapped["Gast"] = relationship()
    positionen: Mapped[list["Rechnungsposition"]] = relationship(
        back_populates="rechnung", cascade="all, delete-orphan"
    )


class Rechnungsposition(Base, IDMixin, TimestampMixin):
    """
    Einzelne Rechnungszeile. `mwstsatz_prozent` ist ein Snapshot des zum
    Leistungsdatum gültigen Satzes – bewusst redundant gespeichert, damit
    spätere MWST-Satzänderungen bestehende Rechnungen nicht verändern.
    """
    __tablename__ = "rechnungsposition"

    rechnung_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("rechnung.id"))
    artikel_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("artikel.id"))
    menge: Mapped[float] = mapped_column(Numeric(8, 2), default=1)
    einzelpreis: Mapped[float] = mapped_column(Numeric(8, 2))
    betrag: Mapped[float] = mapped_column(Numeric(10, 2))
    mwstsatz_prozent: Mapped[float] = mapped_column(Numeric(5, 2))
    mwst_betrag: Mapped[float] = mapped_column(Numeric(10, 2))

    rechnung: Mapped["Rechnung"] = relationship(back_populates="positionen")
    artikel: Mapped["Artikel"] = relationship()
