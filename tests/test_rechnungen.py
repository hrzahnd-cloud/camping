"""Tests: Rechnung aus dem Aufenthalt (Positionen je Saison, Taxen, Anzahlung), Zahlung, Storno, PDF."""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.models.buchung import Aufenthalt, Buchung, Gast
from app.models.reservation import Reservationsanfrage, Zahlung
from app.seed import grunddaten_einspielen
from app.services import leistungen as lst

JAHR = date.today().year


@pytest.fixture
def grunddaten(db):
    grunddaten_einspielen(db)
    db.commit()


def _aufenthalt(db, typ="camper", von=date(2026, 6, 30), bis=date(2026, 7, 2), e=2, k=1, anzahlung=None,
                status="ausgecheckt"):
    anfrage = None
    if anzahlung is not None:
        anfrage = Reservationsanfrage(quelle="manuell", eingangs_datum=datetime(2026, 10, 1, tzinfo=timezone.utc), sprache="de",
                                      gast_name="Rita Rechnung", gast_email="rita@example.com", gewuenscht_von=von,
                                      gewuenscht_bis=bis, stellplatz_typ=typ, anzahl_erwachsene=e, anzahl_kinder=k,
                                      status="angereist")
        db.add(anfrage)
        db.flush()
        db.add(Zahlung(bezug_typ="reservationsanfrage", bezug_id=anfrage.id, betrag=Decimal(anzahlung), zahlungsart="twint",
                       status="eingegangen", eingegangen_am=datetime(2026, 10, 5, tzinfo=timezone.utc)))
    g = Gast(vorname="Rita", nachname="Rechnung", nationalitaet="CH", strasse="Testweg 1", plz="3000", ort="Bern")
    db.add(g)
    db.flush()
    b = Buchung(stellplatz_typ=typ, von=von, bis=bis, anzahl_erwachsene=e, anzahl_kinder=k, status=status,
                hauptgast_id=g.id, reservationsanfrage_id=anfrage.id if anfrage else None)
    b.leistungen = lst.grundzeilen(b)
    db.add(b)
    db.flush()
    db.add(Aufenthalt(buchung_id=b.id, gast_id=g.id, ankunft=von, abreise=bis))
    db.commit()
    return str(b.id)


def test_rechnung_bei_abreise_mit_saisonzeilen_taxen_und_anzahlung(client, db, grunddaten):
    bid = _aufenthalt(db, anzahlung="50")
    r = client.post(f"/rechnungen/aus-aufenthalt/{bid}", json={"zahlungsart": "twint"})
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["nummer"] == f"{JAHR}-1000" and d["status"] == "bezahlt" and d["zahlungsart"] == "twint"
    zeilen = [(p["bezeichnung"], p["menge"], p["einzelpreis"], p["betrag"], p["mwstsatz_prozent"]) for p in d["positionen"]]
    assert zeilen == [
        ("Erwachsene (ab 16), Vorsaison", "2", "7.00", "14.00", "3.8"),
        ("Erwachsene (ab 16), Hauptsaison", "2", "8.00", "16.00", "3.8"),
        ("Kinder (6–15), Vorsaison", "1", "3.40", "3.40", "3.8"),
        ("Kinder (6–15), Hauptsaison", "1", "4.00", "4.00", "3.8"),
        ("Camper, Vorsaison", "1", "16.00", "16.00", "3.8"),
        ("Camper, Hauptsaison", "1", "18.00", "18.00", "3.8"),
        ("Umweltabgabe", "2", "1.00", "2.00", "3.8"),
        ("Kurtaxe Aeschi", "4", "3.50", "14.00", "0"),
        ("Beherbergungsabgabe Kanton Bern", "4", "1.00", "4.00", "0"),
    ]
    assert (d["gesamtbetrag"], d["anzahlung"], d["restbetrag"]) == ("91.40", "50.00", "41.40")
    assert d["reservationsnummer"] is not None
    schluss = db.query(Zahlung).filter_by(bezug_typ="rechnung").one()
    assert (Decimal(str(schluss.betrag)), schluss.zahlungsart) == (Decimal("41.40"), "twint")
    # Aufenthalt ist gesperrt, zweite Rechnung nicht möglich
    auf = client.get(f"/aufenthalte/{bid}").json()
    assert auf["hat_rechnung"] and auf["rechnung_nummer"] == d["nummer"]
    assert client.patch(f"/aufenthalte/{bid}", json={"platz": "9"}).status_code == 400
    assert client.post(f"/rechnungen/aus-aufenthalt/{bid}", json={}).status_code == 400
    # PDF
    pdf = client.get(f"/rechnungen/{d['id']}/pdf")
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf" and pdf.content.startswith(b"%PDF")


def test_rechnung_erst_nach_abreise_und_mit_preisen(client, db, grunddaten):
    da = _aufenthalt(db, status="eingecheckt")
    assert "Abreise" in client.post(f"/rechnungen/aus-aufenthalt/{da}", json={}).json()["detail"]
    winter = _aufenthalt(db, von=date(2026, 11, 2), bis=date(2026, 11, 4))
    r = client.post(f"/rechnungen/aus-aufenthalt/{winter}", json={})
    assert r.status_code == 400 and "fehlt ein Preis" in r.json()["detail"]
    # keine Nummer verbraucht
    ok = client.post(f"/rechnungen/aus-aufenthalt/{_aufenthalt(db)}", json={}).json()
    assert ok["nummer"] == f"{JAHR}-1000"


def test_offen_bezahlen_karte_erst_nach_freigabe(client, db, grunddaten):
    d = client.post(f"/rechnungen/aus-aufenthalt/{_aufenthalt(db)}", json={}).json()
    assert d["status"] == "offen" and d["restbetrag"] == d["gesamtbetrag"]
    assert client.get("/rechnungen/einstellungen").json() == {"karte": False, "zahlungsarten": ["bar", "twint", "ueberweisung"]}
    assert client.post(f"/rechnungen/{d['id']}/bezahlt", json={"zahlungsart": "karte"}).status_code == 400
    client.put("/rechnungen/einstellungen", json={"karte": True})
    r = client.post(f"/rechnungen/{d['id']}/bezahlt", json={"zahlungsart": "karte", "datum": "2026-07-02"}).json()
    assert (r["status"], r["zahlungsart"], r["bezahlt_am"]) == ("bezahlt", "karte", "2026-07-02")
    assert client.post(f"/rechnungen/{d['id']}/bezahlt", json={"zahlungsart": "bar"}).status_code == 400
    liste = client.get("/rechnungen/liste?status=bezahlt").json()
    assert [x["nummer"] for x in liste] == [d["nummer"]] and client.get("/rechnungen/liste?status=offen").json() == []


def test_anzahlung_deckt_alles(client, db, grunddaten):
    d = client.post(f"/rechnungen/aus-aufenthalt/{_aufenthalt(db, anzahlung='200')}", json={}).json()
    assert (d["status"], d["anzahlung"], d["restbetrag"], d["zahlungsart"]) == ("bezahlt", "91.40", "0.00", None)


def test_storno_gibt_aufenthalt_frei_nummer_bleibt(client, db, grunddaten):
    bid = _aufenthalt(db)
    erste = client.post(f"/rechnungen/aus-aufenthalt/{bid}", json={"zahlungsart": "bar"}).json()
    s = client.post(f"/rechnungen/{erste['id']}/stornieren").json()
    assert s["status"] == "storniert" and s["storniert_am"]
    assert db.query(Zahlung).filter_by(bezug_typ="rechnung").one().status == "storniert"
    assert client.patch(f"/aufenthalte/{bid}", json={"platz": "9"}).status_code == 200
    zweite = client.post(f"/rechnungen/aus-aufenthalt/{bid}", json={"zahlungsart": "bar"}).json()
    assert zweite["nummer"] == f"{JAHR}-1001"
    assert client.delete(f"/aufenthalte/{bid}").status_code == 400
    assert client.post(f"/rechnungen/{erste['id']}/stornieren").status_code == 400
    assert client.get(f"/rechnungen/{erste['id']}/pdf").status_code == 200


def test_zwaergli_rechnung_mit_inbegriffenen_personen_und_wassertank(client, db, grunddaten):
    bid = _aufenthalt(db, typ="zwaergli", von=date(2026, 7, 10), bis=date(2026, 7, 12), e=3, k=0)
    client.post(f"/aufenthalte/{bid}/leistungen", json={"art": "wassertank", "von": "2026-07-10"})
    db.query(Buchung).filter_by(id=__import__("uuid").UUID(bid)).update({"status": "ausgecheckt"})
    db.commit()
    d = client.post(f"/rechnungen/aus-aufenthalt/{bid}", json={"zahlungsart": "bar"}).json()
    p = {x["bezeichnung"]: x["betrag"] for x in d["positionen"]}
    assert p["Zwärgli"] == "80.00" and p["Erwachsene (ab 16)"] == "48.00"
    assert p["Inbegriffen im Zwärgli (2 Personen je Nacht)"] == "-32.00"
    assert p["Wassertankfüllung, 10.7. – ab 2 Nächten inbegriffen"] == "0.00"
    assert d["gesamtbetrag"] == "123.00"   # 80 + 48 − 32 + Kurtaxe 21 + Beherbergungsabgabe 6


def test_logo_und_mwst_auf_dem_total(client, db, grunddaten):
    import base64
    from io import BytesIO

    from PIL import Image

    puffer = BytesIO()
    Image.new("RGB", (2000, 1400), (240, 120, 20)).save(puffer, "JPEG")
    url = "data:image/jpeg;base64," + base64.b64encode(puffer.getvalue()).decode()
    assert client.get("/einstellungen/logo").status_code == 404
    assert client.put("/einstellungen/logo", json={"bild": "data:text/plain;base64,aGFsbG8="}).status_code == 400
    assert client.put("/einstellungen/logo", json={"bild": url}).status_code == 204
    logo = client.get("/einstellungen/logo")
    assert logo.status_code == 200 and logo.headers["content-type"] == "image/jpeg"
    assert max(Image.open(BytesIO(logo.content)).size) == 1200   # verkleinert
    # MWST einmal auf dem Total je Satz, unabhängig von der Anzahlung
    d = client.post(f"/rechnungen/aus-aufenthalt/{_aufenthalt(db, anzahlung='50')}", json={"zahlungsart": "bar"}).json()
    basis = sum(Decimal(p["betrag"]) for p in d["positionen"] if p["mwstsatz_prozent"] == "3.8")
    assert d["mwst_betrag_total"] == str((basis - basis / Decimal("1.038")).quantize(Decimal("0.01")))
    pdf = client.get(f"/rechnungen/{d['id']}/pdf")
    assert pdf.status_code == 200 and b"/Subtype /Image" in pdf.content
    assert client.delete("/einstellungen/logo").status_code == 204
    assert client.get("/einstellungen/logo").status_code == 404
