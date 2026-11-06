"""
Modelle: Reservationsanfrage, Zahlung, Zahlungsanbieterkonfiguration.

Siehe Konzeptdokument Abschnitt 10 (Workflow) und 10.4 (Zahlungsarten).

Hinweis zu `Zahlung.bezug_typ`/`bezug_id`: Da eine Zahlung sich wahlweise
auf eine Reservationsanfrage ODER eine Rechnung bezieht, gibt es dafür
bewusst KEINEN echten Fremdschlüssel/keine ORM-Relationship (das würde
zwei nullable FKs oder eine fragile polymorphe Beziehung erfordern).
Die Auflösung erfolgt stattdessen explizit in der Service-Schicht,
z.B. `db.get(Reservationsanfrage, zahlung.bezug_id)` je nach `bezug_typ`
(siehe app/services/zahlungen.py).
"""
import re
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, event, select
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from app.database import Base
from app.models.common import GUID, IDMixin, TimestampMixin


class Reservationsanfrage(Base, IDMixin, TimestampMixin):
    """Eingehende Anfrage (E-Mail/Homepage/manuell), vor Umwandlung in eine Buchung."""
    __tablename__ = "reservationsanfrage"

    nummer: Mapped[str | None] = mapped_column(String(20), index=True, unique=True)
    """Laufnummer «Jahr-Nummer» (z.B. 2026-042), wird beim Anlegen vergeben
    (siehe vergib_nummern). Steht im Betreff jeder Antwort und ordnet
    Rückmeldungen des Gastes sicher zu, auch nach einer Weiterleitung."""

    quelle: Mapped[str] = mapped_column(String(30))
    """email | homepage_formular | manuell"""
    eingangs_datum: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sprache: Mapped[str] = mapped_column(String(2), default="de")
    """de | fr | it | en"""

    mail_message_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    """Message-ID der Original-Mail (Kanal 'email'); verhindert Doppelimporte."""

    gast_name: Mapped[str] = mapped_column(String(200))
    gast_email: Mapped[str] = mapped_column(String(255))
    gast_telefon: Mapped[str | None] = mapped_column(String(50))

    gewuenscht_von: Mapped[date | None] = mapped_column(Date)
    gewuenscht_bis: Mapped[date | None] = mapped_column(Date)
    """Beim Mail-Import ggf. leer, wenn der Zeitraum nicht erkannt wurde
    (Anfrage gilt dann als unvollständig)."""
    stellplatz_typ: Mapped[str | None] = mapped_column(String(50))
    anzahl_erwachsene: Mapped[int] = mapped_column(Integer, default=1)
    anzahl_kinder: Mapped[int] = mapped_column(Integer, default=0)
    bemerkung: Mapped[str | None] = mapped_column(Text)

    rohtext: Mapped[str | None] = mapped_column(Text)
    """Original-Mailinhalt zur Nachvollziehbarkeit (Kanal 'email')."""

    vollstaendig: Mapped[bool] = mapped_column(Boolean, default=False)
    fehlende_angaben: Mapped[str | None] = mapped_column(Text)
    """Kommagetrennte Liste fehlender Pflichtfelder, falls unvollständig."""

    status: Mapped[str] = mapped_column(String(30), default="neu")
    """neu | unvollstaendig | geprueft_vollstaendig | in_abklaerung (freie Antwort/
       Rückfrage gesendet) | erstantwort_gesendet | zahlung_ausstehend |
       bezahlt_akzeptiert | angereist (Aufenthalt erfasst) | nicht_erschienen |
       abgelehnt | storniert"""

    newsletter_einwilligung: Mapped[bool] = mapped_column(Boolean, default=False)
    """Separate Opt-in-Angabe, NICHT vorangehakt (siehe Konzept Abschnitt 11.1)."""

    anzahlung_verlangt: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    """In der Antwort mit Anzahlung verlangter Betrag (CHF). Der tatsächlich
    gutgeschriebene Betrag steht als Zahlung (bezug_typ «reservationsanfrage»)."""


NUMMER_RE = re.compile(r"\b(20\d{2}-\d{3,5})\b")


def _naechste_nummer(session: Session, jahr: int, vergeben: dict[int, int]) -> str:
    if jahr not in vergeben:
        vorhandene = session.execute(
            select(Reservationsanfrage.nummer).where(Reservationsanfrage.nummer.like(f"{jahr}-%"))
        ).scalars().all()
        vergeben[jahr] = max((int(n.split("-", 1)[1]) for n in vorhandene if n), default=0)
    vergeben[jahr] += 1
    return f"{jahr}-{vergeben[jahr]:03d}"


@event.listens_for(Session, "before_flush")
def vergib_nummern(session: Session, _kontext, _instanzen) -> None:
    """Jede neue Anfrage bekommt ihre Nummer, egal über welchen Weg sie angelegt wird."""
    neue = sorted((o for o in session.new if isinstance(o, Reservationsanfrage) and not o.nummer),
                  key=lambda a: a.eingangs_datum or datetime.now(timezone.utc))
    if not neue:
        return
    vergeben: dict[int, int] = {}
    with session.no_autoflush:
        for anfrage in neue:
            jahr = (anfrage.eingangs_datum or datetime.now(timezone.utc)).year
            anfrage.nummer = _naechste_nummer(session, jahr, vergeben)


class Zahlungsanbieterkonfiguration(Base, IDMixin, TimestampMixin):
    """
    Zugangsdaten/Status externer Zahlungsanbieter.

    AKTUELL NUR VORBEREITET: `aktiv` bleibt False, bis ein Anbieter
    (z.B. Saferpay/Datatrans/Stripe) unter Vertrag ist (siehe Konzept 10.4).
    """
    __tablename__ = "zahlungsanbieterkonfiguration"

    zahlungsart: Mapped[str] = mapped_column(String(30), default="kreditkarte")
    anbieter: Mapped[str | None] = mapped_column(String(100))
    aktiv: Mapped[bool] = mapped_column(Boolean, default=False)
    zugangsdaten_verschluesselt: Mapped[str | None] = mapped_column(Text)
    webhook_url: Mapped[str | None] = mapped_column(String(300))


class Zahlung(Base, IDMixin, TimestampMixin):
    """
    Zahlungseingang/-versuch zu einer Reservationsanfrage (Anzahlung)
    ODER einer Rechnung (Schlusszahlung) – siehe Konzept Abschnitt 12.2.
    """
    __tablename__ = "zahlung"

    bezug_typ: Mapped[str] = mapped_column(String(30))
    """reservationsanfrage | rechnung"""
    bezug_id: Mapped[uuid.UUID] = mapped_column(GUID())
    """Verweist je nach bezug_typ auf Reservationsanfrage.id oder Rechnung.id
    (kein DB-Fremdschlüssel möglich, da polymorph – siehe Moduldocstring)."""

    betrag: Mapped[float] = mapped_column(Numeric(10, 2))
    waehrung: Mapped[str] = mapped_column(String(3), default="CHF")
    zahlungsart: Mapped[str] = mapped_column(String(30))
    """banküberweisung | twint | kreditkarte | bar"""
    status: Mapped[str] = mapped_column(String(30), default="ausstehend")
    """ausstehend | eingegangen | fehlgeschlagen | storniert"""
    referenz: Mapped[str | None] = mapped_column(String(100))
    eingegangen_am: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    abgeglichen_von: Mapped[str | None] = mapped_column(String(100))
    """Benutzername bei manuellem Abgleich, oder 'system' bei künftiger Automatik."""

    zahlungsanbieterkonfiguration_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("zahlungsanbieterkonfiguration.id")
    )
