"""Tests für die Vorbereitung der Feratel-Gästemeldung (manueller WebClient-Weg)."""
from datetime import date

import pytest

from app.models import Aufenthalt, Buchung, Campingplatz, Gast, Stellplatz


@pytest.fixture
def buchung(db):
    camping = Campingplatz(name="Camping Aeschi")
    db.add(camping)
    db.flush()
    platz = Stellplatz(campingplatz_id=camping.id, bezeichnung="A1", typ="zeltwiese")
    haupt = Gast(vorname="Anna", nachname="Muster", land="DE", nationalitaet="DE",
                 plz="10115", ort="Berlin", email="anna@example.de", geburtsdatum=date(1985, 3, 3))
    kind = Gast(vorname="Max", nachname="Muster", geburtsdatum=date(2022, 5, 1))
    db.add_all([platz, haupt, kind])
    db.flush()
    b = Buchung(stellplatz_id=platz.id, von=date(2026, 7, 10), bis=date(2026, 7, 15), hauptgast_id=haupt.id)
    db.add(b)
    db.flush()
    for g in (haupt, kind):
        db.add(Aufenthalt(buchung_id=b.id, gast_id=g.id, ankunft=date(2026, 7, 10), abreise=date(2026, 7, 15)))
    db.commit()
    return b


def test_fehlende_pflichtangaben_werden_gemeldet(client, buchung):
    daten = client.get(f"/feratel/meldeschein/{buchung.id}").json()
    assert daten["vollstaendig"] is False
    assert daten["fehlende_angaben"] == ["Hauptgast: Strasse"]
    assert daten["anzahl_personen"] == 2
    assert daten["ankunft"] == "2026-07-10" and daten["abreise"] == "2026-07-15"
    assert daten["begleitpersonen"][0]["alter"] == 4
    assert any("unter 6 Jahren" in h for h in daten["hinweise"])


def test_vollstaendig_sobald_strasse_vorhanden(client, db, buchung):
    buchung.hauptgast.strasse = "Hauptstrasse 1"
    db.commit()
    daten = client.get(f"/feratel/meldeschein/{buchung.id}").json()
    assert daten["vollstaendig"] is True


def test_erfasster_meldeschein_wird_protokolliert_und_nicht_doppelt(client, buchung):
    erste = client.post(f"/feratel/meldeschein/{buchung.id}/erfasst", json={"meldescheinnummer": "MS-4711"})
    assert erste.status_code == 201 and erste.json()["aufenthalte"] == 2
    zweite = client.post(f"/feratel/meldeschein/{buchung.id}/erfasst", json={"meldescheinnummer": "MS-4712"})
    assert zweite.status_code == 409 and "MS-4711" in zweite.json()["detail"]


def test_unbekannte_buchung_gibt_404(client):
    assert client.get("/feratel/meldeschein/00000000-0000-0000-0000-000000000000").status_code == 404
