"""
Smoke-Test: erzeugt alle Tabellen in einer temporären SQLite-Datenbank
und legt einen minimalen Datensatz an. Dient als schneller Nachweis,
dass das Datenmodell konsistent ist, BEVOR gegen eine echte
PostgreSQL-Instanz migriert wird.

Hinweis: SQLite dient hier nur als Schnelltest für die Modellstruktur.
Produktiv wird ausschliesslich PostgreSQL verwendet (u.a. wegen
`func.to_char` in den Auswertungen, das PostgreSQL-spezifisch ist).

Ausführen mit:  pytest tests/test_models_smoke.py -v
"""
import uuid
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Campingplatz, Stellplatz, Gast, Buchung, Aufenthalt


def test_tabellen_erzeugen_und_grunddatensatz_anlegen():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    campingplatz = Campingplatz(name="Camping Aeschi", gemeinde="Aeschi")
    db.add(campingplatz)
    db.flush()

    stellplatz = Stellplatz(
        campingplatz_id=campingplatz.id, bezeichnung="Zeltwiese A1", typ="zelt"
    )
    db.add(stellplatz)
    db.flush()

    gast = Gast(vorname="Max", nachname="Muster", land="CH")
    db.add(gast)
    db.flush()

    buchung = Buchung(
        stellplatz_id=stellplatz.id,
        von=date(2026, 8, 10),
        bis=date(2026, 8, 15),
        hauptgast_id=gast.id,
        status="bestaetigt",
    )
    db.add(buchung)
    db.flush()

    aufenthalt = Aufenthalt(
        buchung_id=buchung.id, gast_id=gast.id,
        ankunft=date(2026, 8, 10), abreise=date(2026, 8, 15),
    )
    db.add(aufenthalt)
    db.commit()

    assert aufenthalt.anzahl_naechte == 5
    assert db.get(Buchung, buchung.id).stellplatz.bezeichnung == "Zeltwiese A1"

    db.close()


if __name__ == "__main__":
    test_tabellen_erzeugen_und_grunddatensatz_anlegen()
    print("Smoke-Test erfolgreich: Datenmodell konsistent.")
