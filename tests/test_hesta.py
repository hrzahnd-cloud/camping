"""Tests für Aggregation, PDF/CSV-Export und Versand der HESTA-Monatsmeldung."""
from datetime import date

import pytest

from app.config import Settings, get_settings
from app.main import app
from app.models import Aufenthalt, Buchung, Campingplatz, Gast, Rechnung, Stellplatz
from app.services.hesta import aggregiere_hesta_monat
from app.services.hesta_export import (
    HestaBericht,
    erzeuge_hesta_csv,
    erzeuge_hesta_mail,
    erzeuge_hesta_pdf,
)


def _aufenthalt(db, platz, land, ankunft, abreise, bezahlt=True, nummer="2026-1000"):
    gast = Gast(vorname="Test", nachname=land, land=land)
    db.add(gast)
    db.flush()
    buchung = Buchung(stellplatz_id=platz.id, von=ankunft, bis=abreise, hauptgast_id=gast.id)
    db.add(buchung)
    db.flush()
    db.add(Aufenthalt(buchung_id=buchung.id, gast_id=gast.id, ankunft=ankunft, abreise=abreise))
    db.add(Rechnung(
        buchung_id=buchung.id, kunde_id=gast.id, nummer=nummer, datum=abreise,
        status="bezahlt" if bezahlt else "offen",
    ))
    db.flush()


@pytest.fixture
def betrieb(db):
    camping = Campingplatz(
        name="Camping Aeschi", adresse="Seestrasse 1", gemeinde="Aeschi",
        bur_nummer="12345678", hesta_anzahl_zimmer=20, hesta_anzahl_betten=60,
    )
    db.add(camping)
    db.flush()
    platz = Stellplatz(campingplatz_id=camping.id, bezeichnung="Zeltwiese A1", typ="zeltwiese")
    db.add(platz)
    db.flush()
    _aufenthalt(db, platz, "CH", date(2026, 7, 10), date(2026, 7, 15), nummer="2026-1000")
    _aufenthalt(db, platz, "DE", date(2026, 7, 30), date(2026, 8, 3), nummer="2026-1001")
    _aufenthalt(db, platz, "FR", date(2026, 7, 5), date(2026, 7, 7), bezahlt=False, nummer="2026-1002")
    _aufenthalt(db, platz, "SE", date(2026, 7, 20), date(2026, 7, 22), nummer="2026-1003")
    db.commit()
    return camping


def test_aggregation_juli_zaehlt_ankuenfte_und_naechte(db, betrieb):
    juli = {p.land: p for p in aggregiere_hesta_monat(db, 2026, 7)}
    assert (juli["CH"].anzahl_personen, juli["CH"].anzahl_uebernachtungen) == (1, 5)
    assert (juli["DE"].anzahl_personen, juli["DE"].anzahl_uebernachtungen) == (1, 2)
    assert "FR" not in juli  # Rechnung nicht bezahlt


def test_aggregation_august_hat_naechte_aber_keine_ankunft(db, betrieb):
    august = {p.land: p for p in aggregiere_hesta_monat(db, 2026, 8)}
    assert (august["DE"].anzahl_personen, august["DE"].anzahl_uebernachtungen) == (0, 2)


def test_pdf_csv_und_mail(db, betrieb):
    bericht = HestaBericht(
        betrieb_name="Camping Aeschi", jahr=2026, monat=7,
        positionen=aggregiere_hesta_monat(db, 2026, 7),
        bur_nummer="12345678", anzahl_zimmer=20, anzahl_betten=60,
        schliessungstage=[(date(2026, 7, 1), date(2026, 7, 3))],
    )
    pdf = erzeuge_hesta_pdf(bericht)
    assert pdf.startswith(b"%PDF")

    zeilen = erzeuge_hesta_csv(bericht).splitlines()
    assert zeilen[0] == "bur_nummer;jahr;monat;land;anzahl_personen;anzahl_uebernachtungen"
    assert "12345678;2026;7;CH;1;5" in zeilen
    assert "12345678;2026;7;SE;1;2" in zeilen

    mail = erzeuge_hesta_mail(bericht, "info@camping-aeschi.ch", "hotelstatistik@bfs.admin.ch", pdf, "x")
    assert mail["Subject"] == "HESTA-Meldung 12345678 07/2026"
    assert [t.get_filename() for t in mail.iter_attachments()] == ["hesta_2026-07.pdf", "hesta_2026-07.csv"]


def test_vorschau_endpoint_meldet_fehlende_betriebsdaten(client, db):
    db.add(Campingplatz(name="Camping Aeschi"))
    db.commit()
    daten = client.get("/hesta/vorschau", params={"jahr": 2026, "monat": 7}).json()
    assert any("BUR-Nummer" in w for w in daten["warnungen"])
    assert daten["total_uebernachtungen"] == 0


def test_pdf_und_csv_endpoint(client, betrieb):
    pdf = client.get("/hesta/pdf", params={"jahr": 2026, "monat": 7})
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    csv = client.get("/hesta/csv", params={"jahr": 2026, "monat": 7})
    assert "CH;1;5" in csv.text


def test_meldung_erzeugen_einfrieren_und_manuell_einreichen(client, betrieb):
    antwort = client.post("/hesta/meldungen", json={
        "jahr": 2026, "monat": 7, "schliessungstage": [["2026-07-01", "2026-07-03"]], "bemerkung": "Test",
    })
    assert antwort.status_code == 201
    meldung = antwort.json()
    assert meldung["status"] == "entwurf" and meldung["total_uebernachtungen"] == 9

    assert client.get(f"/hesta/meldungen/{meldung['id']}/pdf").content.startswith(b"%PDF")
    erledigt = client.post(f"/hesta/meldungen/{meldung['id']}/als-eingereicht-markieren").json()
    assert erledigt["status"] == "eingereicht" and erledigt["versandart"] == "manuell_pdf"

    zweite = client.post("/hesta/meldungen", json={"jahr": 2026, "monat": 7})
    assert zweite.status_code == 409


def test_versand_ist_standardmaessig_gesperrt(client, betrieb):
    meldung = client.post("/hesta/meldungen", json={"jahr": 2026, "monat": 7}).json()
    assert client.post(f"/hesta/meldungen/{meldung['id']}/versenden").status_code == 409


def test_versand_mit_aktivierung_schickt_mail(client, betrieb, monkeypatch):
    gesendet = []
    monkeypatch.setattr("app.routers.hesta.sende_mail", lambda settings, msg: gesendet.append(msg))
    app.dependency_overrides[get_settings] = lambda: Settings(
        hesta_email_versand_aktiv=True, smtp_host="smtp.test", _env_file=None
    )
    try:
        meldung = client.post("/hesta/meldungen", json={"jahr": 2026, "monat": 7}).json()
        antwort = client.post(f"/hesta/meldungen/{meldung['id']}/versenden")
    finally:
        app.dependency_overrides.pop(get_settings, None)
    assert antwort.status_code == 200
    assert antwort.json()["versandart"] == "email"
    assert gesendet[0]["To"] == "hotelstatistik@bfs.admin.ch"
