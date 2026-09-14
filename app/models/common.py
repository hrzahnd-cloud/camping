"""
Gemeinsame Bausteine für alle ORM-Modelle: UUID-Primärschlüssel und
Zeitstempel. Bewusst als Mixin statt Vererbung von einer konkreten
Basisklasse, damit jedes Modell flexibel bleibt.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import CHAR, TypeDecorator


class GUID(TypeDecorator):
    """Plattformunabhängiger UUID-Typ: nativ in PostgreSQL, als CHAR(36) sonst."""
    impl = CHAR(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import UUID as PG_UUID
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return str(value)
        if not isinstance(value, uuid.UUID):
            return str(uuid.UUID(value))
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(value)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IDMixin:
    """Primärschlüssel als UUID, serverseitig per Default erzeugt."""
    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    """Erstellungs-/Änderungszeitpunkt, automatisch gepflegt."""
    erstellt_am: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    geaendert_am: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
