"""
Newsletter-Modelle (siehe Konzeptdokument Abschnitt 11).

Wichtig: `NewsletterAbo` ist die führende Quelle für die Einwilligung
(rechtlich relevant, revDSG/UWG). Mailchimp ist die führende Quelle für
Versand/Statistik – siehe app/services/mailchimp_client.py (Stub).
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import GUID, IDMixin, TimestampMixin


class MailchimpKonfiguration(Base, IDMixin, TimestampMixin):
    """Zugangsdaten/Status der Mailchimp-Anbindung (ein Datensatz pro Installation)."""
    __tablename__ = "mailchimp_konfiguration"

    api_key_verschluesselt: Mapped[str | None] = mapped_column(Text)
    server_prefix: Mapped[str | None] = mapped_column(String(10))
    """z.B. 'us21' – Teil des Mailchimp-API-Endpunkts."""
    audience_id: Mapped[str | None] = mapped_column(String(50))
    aktiv: Mapped[bool] = mapped_column(Boolean, default=False)
    webhook_url: Mapped[str | None] = mapped_column(String(300))


class NewsletterAbo(Base, IDMixin, TimestampMixin):
    """Einwilligung/Abmeldung einer E-Mail-Adresse, unabhängig von einzelner Buchung."""
    __tablename__ = "newsletter_abo"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    vorname: Mapped[str | None] = mapped_column(String(100))
    sprache: Mapped[str] = mapped_column(String(2), default="de")
    status: Mapped[str] = mapped_column(String(20), default="angemeldet")
    """angemeldet | abgemeldet"""
    einwilligung_am: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    einwilligung_quelle: Mapped[str | None] = mapped_column(String(50))
    """reservationsanfrage_checkbox | checkin_formular | manuell"""
    abgemeldet_am: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    mailchimp_member_id: Mapped[str | None] = mapped_column(String(100))
    mailchimp_sync_status: Mapped[str] = mapped_column(String(20), default="offen")
    """offen | synchronisiert | fehler"""


class NewsletterKampagne(Base, IDMixin, TimestampMixin):
    """Einzelner Newsletter-Versand (Inhalt, Sprache, Status)."""
    __tablename__ = "newsletter_kampagne"

    titel: Mapped[str] = mapped_column(String(200))
    sprache: Mapped[str] = mapped_column(String(2))
    betreff: Mapped[str] = mapped_column(String(300))
    inhalt: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="entwurf")
    """entwurf | geplant | versendet"""
    geplant_am: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    versendet_am: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    erstellt_von: Mapped[str | None] = mapped_column(String(100))
    mailchimp_campaign_id: Mapped[str | None] = mapped_column(String(100))

    versaende: Mapped[list["NewsletterVersand"]] = relationship(back_populates="kampagne")


class NewsletterVersand(Base, IDMixin, TimestampMixin):
    """Lokaler Spiegel je Empfänger einer Kampagne (Mailchimp führt die Primärstatistik)."""
    __tablename__ = "newsletter_versand"

    kampagne_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("newsletter_kampagne.id"))
    newsletter_abo_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("newsletter_abo.id"))
    gesendet_am: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="zugestellt")
    """zugestellt | fehler | abgeprallt"""
    abmeldelink_verwendet_am: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    kampagne: Mapped["NewsletterKampagne"] = relationship(back_populates="versaende")
    abo: Mapped["NewsletterAbo"] = relationship()
