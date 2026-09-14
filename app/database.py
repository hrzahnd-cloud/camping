"""
Datenbankanbindung (SQLAlchemy 2.0, PostgreSQL).

Die App verwendet ausschliesslich portable, PostgreSQL-kompatible
Konstrukte (keine proprietären PG-Erweiterungen ausser dem nativen
UUID-Typ), damit lokale Tests auch mit SQLite laufen können.
"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    """Gemeinsame Basisklasse für alle ORM-Modelle."""
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI-Dependency: liefert eine DB-Session je Request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
