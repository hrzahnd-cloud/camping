"""
Modelle für externe Meldungen: Feratel (Kurtaxe/Beherbergungsabgabe) und
HESTA (Beherbergungsstatistik BFS). Siehe Konzeptdokument Abschnitte 5, 6.

WICHTIG: Der tatsächliche Versand (SOAP/XML an Feratel) ist NICHT
implementiert, siehe app/services/feratel_client.py (Stub) – dafür
fehlt aktuell die WSDL/technische Dokumentation von Thun-Thunersee
Tourismus (PMS-Partner-Freischaltung noch offen, siehe Konzeptdokument).
"""
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import GUID, IDMixin, TimestampMixin


class FeratelKonfiguration(Base, IDMixin, TimestampMixin):
    """Zugangsdaten für die Feratel Deskline 3.0 VT PMS Web Services (ein Datensatz)."""
    __tablename__ = "feratel_konfiguration"

    gemeinde_nummer: Mapped[str | None] = mapped_column(String(20))
    firmen_nummer: Mapped[str | None] = mapped_column(String(20))
    """Mapping-Code, von Feratel/Tourismusorganisation nach Freischaltung vergeben."""
    endpoint_url: Mapped[str | None] = mapped_column(String(300))
    aktiv: Mapped[bool] = mapped_column(default=False)


class FeratelMeldung(Base, IDMixin, TimestampMixin):
    """Protokoll je Übertragungsversuch eines Aufenthalts an Feratel."""
    __tablename__ = "feratel_meldung"

    aufenthalt_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("aufenthalt.id"))
    gesendet_am: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    xml_payload: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="offen")
    """offen | erfolgreich | fehler"""
    fehlercode: Mapped[str | None] = mapped_column(String(50))
    antwort_roh: Mapped[str | None] = mapped_column(Text)

    aufenthalt: Mapped["Aufenthalt"] = relationship()


class HestaMeldung(Base, IDMixin, TimestampMixin):
    """Monatliche HESTA-Meldeperiode (BFS-Beherbergungsstatistik)."""
    __tablename__ = "hesta_meldung"

    monat: Mapped[int] = mapped_column(Integer)
    jahr: Mapped[int] = mapped_column(Integer)
    generiert_am: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="entwurf")
    """entwurf | exportiert | eingereicht"""
    pdf_pfad: Mapped[str | None] = mapped_column(String(500))

    positionen: Mapped[list["HestaMeldungPosition"]] = relationship(
        back_populates="hesta_meldung", cascade="all, delete-orphan"
    )


class HestaMeldungPosition(Base, IDMixin, TimestampMixin):
    """Aggregierte Zeile je Land für eine HESTA-Meldung."""
    __tablename__ = "hesta_meldung_position"

    hesta_meldung_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("hesta_meldung.id"))
    land: Mapped[str] = mapped_column(String(2))
    """ISO-3166-1 alpha-2"""
    anzahl_personen: Mapped[int] = mapped_column(Integer, default=0)
    anzahl_uebernachtungen: Mapped[int] = mapped_column(Integer, default=0)

    hesta_meldung: Mapped["HestaMeldung"] = relationship(back_populates="positionen")
