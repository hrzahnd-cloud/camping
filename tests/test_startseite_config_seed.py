"""Tests für Startseite, Aufbau der Datenbank-URL und Grunddaten beim Start."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import seed as seed_modul
from app.config import Settings
from app.main import app
from app.models import Artikel, Base, Mwstsatz


def test_startseite_ohne_gebaute_oberflaeche_leitet_auf_api_doku(monkeypatch, tmp_path):
    import app.main as hauptmodul

    monkeypatch.setattr(hauptmodul, "OBERFLAECHE", tmp_path)
    antwort = TestClient(app).get("/", follow_redirects=False)
    assert antwort.status_code in (302, 307)
    assert antwort.headers["location"] == "/docs"


def test_startseite_liefert_gebaute_oberflaeche(monkeypatch, tmp_path):
    import app.main as hauptmodul

    (tmp_path / "index.html").write_text('<!doctype html><div id="root"></div>', encoding="utf-8")
    monkeypatch.setattr(hauptmodul, "OBERFLAECHE", tmp_path)
    antwort = TestClient(app).get("/")
    assert antwort.status_code == 200
    assert '<div id="root">' in antwort.text
    assert antwort.headers["cache-control"] == "no-cache"


@pytest.mark.parametrize("passwort", ["einfach123", "p@ss", "a/b:c", "x#y?z", "e%f", "ä ö+ü"])
def test_db_passwort_mit_sonderzeichen_wird_korrekt_maskiert(monkeypatch, passwort):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    s = Settings(_env_file=None, db_host="db", db_user="camping_user", db_password=passwort)
    url = make_url(s.database_url)
    assert url.password == passwort
    assert url.host == "db"
    assert url.username == "camping_user"
    assert url.database == "campingverwaltung"


def test_alembic_url_uebersteht_configparser_interpolation(monkeypatch):
    """Ein maskiertes Passwort enthält '%'; alembic.ini darf daran nicht scheitern."""
    from alembic.config import Config

    monkeypatch.delenv("DATABASE_URL", raising=False)
    s = Settings(_env_file=None, db_password="p@ss%")
    cfg = Config()
    cfg.set_main_option("sqlalchemy.url", s.database_url.replace("%", "%%"))
    assert make_url(cfg.get_main_option("sqlalchemy.url")).password == "p@ss%"


@pytest.fixture
def leere_db(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    fabrik = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(seed_modul, "SessionLocal", fabrik)
    yield fabrik
    engine.dispose()


def test_grunddaten_nur_in_leere_datenbank(leere_db):
    assert seed_modul.seed_falls_leer() is True
    with leere_db() as db:
        artikel = db.scalar(select(func.count()).select_from(Artikel))
        mwst = db.scalar(select(func.count()).select_from(Mwstsatz))
    assert artikel > 0 and mwst == 3

    # zweiter Start: nichts doppelt, kein Fehler
    assert seed_modul.seed_falls_leer() is False
    with leere_db() as db:
        assert db.scalar(select(func.count()).select_from(Artikel)) == artikel
        assert db.scalar(select(func.count()).select_from(Mwstsatz)) == 3
