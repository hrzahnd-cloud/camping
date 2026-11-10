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
    """`bezahlt=False` steht neu für einen stornierten Aufenthalt (zählt nicht)."""
    gast = Gast(vorname="Test", nachname=land, land=land, nationalitaet=land)
    db.add(gast)
    db.flush()
    buchung = Buchung(stellplatz_id=platz.id, von=ankunft, bis=abreise, hauptgast_id=gast.id,
                      status="ausgecheckt" if bezahlt else "storniert", anzahl_erwachsene=1)
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
    assert "FR" not in juli  # storniert
    assert [p.name for p in aggregiere_hesta_monat(db, 2026, 7)] == ["Deutschland", "Schweden", "Schweiz"]  # alphabetisch


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



def test_alle_personen_nach_nationalitaet_erste_nacht_als_ankunft(client, db):
    from app.services import leistungen as lst
    gast = Gast(vorname="Familie", nachname="Österreich", land="DE", nationalitaet="AT")
    db.add(gast)
    db.flush()
    b = Buchung(stellplatz_typ="wohnwagen", von=date(2026, 7, 30), bis=date(2026, 8, 2), anzahl_erwachsene=2,
                anzahl_kinder=1, anzahl_kleinkinder=1, status="ausgecheckt", hauptgast_id=gast.id)
    b.leistungen = lst.grundzeilen(b)
    db.add(b)
    db.commit()
    juli = {p.land: p for p in aggregiere_hesta_monat(db, 2026, 7)}
    assert (juli["AT"].name, juli["AT"].anzahl_personen, juli["AT"].anzahl_uebernachtungen) == ("Österreich", 4, 8)
    aug = {p.land: p for p in aggregiere_hesta_monat(db, 2026, 8)}
    assert (aug["AT"].anzahl_personen, aug["AT"].anzahl_uebernachtungen) == (0, 4)
    v = client.get("/hesta/vorschau", params={"jahr": 2026, "monat": 7}).json()
    assert v["positionen"][0]["name"] == "Österreich" and v["total_personen"] == 4


def test_faellige_meldung_bis_eingereicht(client, db):
    f = client.get("/hesta/faellig").json()
    assert f["faellig"] is True and f["status"] == "offen"
    m = client.post("/hesta/meldungen", json={"jahr": f["jahr"], "monat": f["monat"]}).json()
    client.post(f"/hesta/meldungen/{m['id']}/als-eingereicht-markieren")
    assert client.get("/hesta/faellig").json()["faellig"] is False


def test_bfs_mail_import_und_einfuegen(client, db):
    from email.message import EmailMessage

    from app.services.mailverlauf import verarbeite_mail
    msg = EmailMessage()
    msg["From"] = "HESTA <noreply@bfs.admin.ch>"
    msg["To"] = "camping@example.com"
    msg["Subject"] = "HESTA: Ihre Zugangsdaten für Oktober 2026"
    msg["Message-ID"] = "<hesta-1@bfs.admin.ch>"
    msg["Date"] = "Sun, 01 Nov 2026 06:00:00 +0100"
    msg.set_content("Benutzername: TEST123\nPasswort: geheim-test")
    art, anfrage = verarbeite_mail(db, msg, Settings(_env_file=None))
    assert (art, anfrage) == ("hesta", None)
    assert verarbeite_mail(db, msg, Settings(_env_file=None))[0] == "duplikat"
    mails = client.get("/hesta/zugangsmails").json()
    assert mails[0]["betreff"].startswith("HESTA: Ihre Zugangsdaten") and "TEST123" in mails[0]["text"]
    assert client.get("/einstellungen/postfach").json()["nicht_zugeordnet"] == []  # nicht bei den Reservations-Mails
    r = client.post("/hesta/zugangsmails", json={"text": "Von: BFS <hesta@bfs.admin.ch>\nBetreff: Zugang Nov\n\nBenutzer: X"})
    assert r.status_code == 201 and r.json()["betreff"] == "Zugang Nov" and r.json()["von"].startswith("BFS")
    assert len(client.get("/hesta/zugangsmails").json()) == 2
    assert client.delete(f"/hesta/zugangsmails/{r.json()['id']}").status_code == 204
