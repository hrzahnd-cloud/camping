"""Modelle: EmailVorlage (Vorlagenbibliothek), EmailVersand (Protokoll)."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
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
    __table_args__ = (UniqueConstraint("typ", "sprache", name="uq_email_vorlage_typ_sprache"),)

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


class MailNachricht(Base, IDMixin, TimestampMixin):
    """
    Mailverlauf einer Reservationsanfrage aus dem Postfach: eingehende Mails
    (Anfrage, Rückfragen des Gastes) und ausgehende Antworten, die ausserhalb
    des Tools geschrieben und per BCC/Umleiten ins Tool-Postfach gelangt sind.
    Antworten, die im Tool vorbereitet wurden, stehen in `email_versand`.
    """
    __tablename__ = "mail_nachricht"

    reservationsanfrage_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("reservationsanfrage.id"), index=True
    )
    """NULL = konnte keiner Anfrage zugeordnet werden (in den Einstellungen sichtbar)."""
    richtung: Mapped[str] = mapped_column(String(10))
    """eingang | ausgang"""
    message_id: Mapped[str] = mapped_column(String(255), unique=True)
    """Message-ID der (ursprünglichen) Mail oder eine Prüfsumme, verhindert Doppelimporte."""
    in_reply_to: Mapped[str | None] = mapped_column(String(255))
    verweise: Mapped[str | None] = mapped_column(Text)
    """Inhalt des References-Headers (Leerzeichen-getrennt)."""
    von: Mapped[str] = mapped_column(String(255))
    an: Mapped[str | None] = mapped_column(String(500))
    betreff: Mapped[str] = mapped_column(String(300), default="")
    text: Mapped[str] = mapped_column(Text, default="")
    datum: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    weitergeleitet: Mapped[bool] = mapped_column(Boolean, default=False)
    """True, wenn die Mail weitergeleitet ankam und ausgepackt wurde."""
    gelesen: Mapped[bool] = mapped_column(Boolean, default=True)
    """False bei neuen Mails des Gastes, bis jemand die Anfrage öffnet."""
    kategorie: Mapped[str | None] = mapped_column(String(20), index=True)
    """NULL = Reservations-Mail; «hesta» = Mail des BFS mit Zugangsdaten (Modul HESTA)."""
