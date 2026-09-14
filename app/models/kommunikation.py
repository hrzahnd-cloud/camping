"""Modelle: EmailVorlage (Vorlagenbibliothek), EmailVersand (Protokoll)."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import GUID, IDMixin, TimestampMixin


class EmailVorlage(Base, IDMixin, TimestampMixin):
    """
    Editierbare Antwortmail-Vorlage je Vorlagentyp und Sprache.

    Ein Vorlagentyp x 4 Sprachen (DE/FR/IT/EN) = 4 unabhängige Datensätze.
    Verfügbare Platzhalter u.a.: {{gastName}}, {{zeitraum}}, {{stellplatzTyp}},
    {{betrag}}, {{iban}}, {{zahlungsfrist}}, {{rechnungsnummer}}
    """
    __tablename__ = "email_vorlage"

    typ: Mapped[str] = mapped_column(String(50))
    """erstantwort_zahlungsinfo | rechnung | (später: zahlungserinnerung, absage, ...)"""
    sprache: Mapped[str] = mapped_column(String(2))
    """de | fr | it | en"""
    betreff: Mapped[str] = mapped_column(String(300))
    koerper: Mapped[str] = mapped_column(Text)
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True)
    zuletzt_geaendert_von: Mapped[str | None] = mapped_column(String(100))


class EmailVersand(Base, IDMixin, TimestampMixin):
    """
    Protokoll je versendeter E-Mail (Reservationsantwort oder Rechnung).

    Generalisiert über bezug_typ/bezug_id, damit derselbe Mechanismus für
    mehrere Belegtypen funktioniert (siehe Konzept Abschnitt 12.1).
    """
    __tablename__ = "email_versand"

    bezug_typ: Mapped[str] = mapped_column(String(30))
    """reservationsanfrage | rechnung"""
    bezug_id: Mapped[uuid.UUID] = mapped_column(GUID())
    vorlage_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("email_vorlage.id"))
    gesendet_von: Mapped[str] = mapped_column(String(100))
    """Benutzer, der den Versand ausgelöst hat (kein vollautomatischer Versand)."""
    empfaenger: Mapped[str] = mapped_column(String(255))
    betreff_final: Mapped[str] = mapped_column(String(300))
    koerper_final: Mapped[str] = mapped_column(Text)
    anhang_pfad: Mapped[str | None] = mapped_column(String(500))
    """Bei Rechnungsversand: Pfad zum angehängten PDF."""
    status: Mapped[str] = mapped_column(String(20), default="gesendet")
    """gesendet | fehler"""
    gesendet_am: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    vorlage: Mapped["EmailVorlage"] = relationship()
