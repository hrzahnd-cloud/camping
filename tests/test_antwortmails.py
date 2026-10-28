"""Tests: Betriebsangaben, Vorlagen in 4 Sprachen, Antwort vorbereiten und protokollieren."""
from datetime import date
from decimal import Decimal

from app.services import antwortmail as am

BETRIEB = {
    "signatur": "Muster Camping\nBeispielweg 1\n3700 Spiez",
    "infoblock": "Check-in 14.00 – 19.00\nHausregeln: https://example.ch/hausregeln.pdf",
    "iban": "CH00 0000 0000 0000 0000 0",
    "bic": "TESTCH22",
    "kontoinhaber": "",
    "twint": "",
}


def _anfrage(client, **felder):
    daten = {
        "quelle": "email", "eingangs_datum": "2026-10-28T10:00:00+01:00", "sprache": "en",
        "gast_name": "Mia Beispiel", "gast_email": "mia@example.com",
        "gewuenscht_von": "2027-07-02", "gewuenscht_bis": "2027-07-05",
        "stellplatz_typ": "wohnwagen", "anzahl_erwachsene": 3, "anzahl_kinder": 0,
    }
    daten.update(felder)
    return client.post("/reservationsanfragen", json=daten).json()


def test_betriebsangaben_speichern_und_lesen(client):
    leer = {f["schluessel"]: f["wert"] for f in client.get("/einstellungen/betrieb").json()}
    assert leer == {k: "" for k in BETRIEB}
    r = client.put("/einstellungen/betrieb", json=BETRIEB)
    assert r.status_code == 200
    assert {f["schluessel"]: f["wert"] for f in r.json()}["iban"] == BETRIEB["iban"]
    assert client.put("/einstellungen/betrieb", json={"passwort": "x"}).status_code == 400


def test_startvorlagen_in_vier_sprachen_und_idempotent(client):
    vorlagen = client.get("/email-vorlagen").json()
    assert [v["sprache"] for v in vorlagen] == ["de", "fr", "it", "en"]
    assert len(client.get("/email-vorlagen").json()) == 4  # kein zweites Mal angelegt


def test_vorlage_bearbeiten_und_platzhalter_pruefen(client):
    de = client.get("/email-vorlagen").json()[0]
    neu = de["koerper"].replace("Wir freuen uns auf Ihren Besuch.", "Bis bald in Aeschi!")
    r = client.put(f"/email-vorlagen/{de['id']}", json={"betreff": de["betreff"], "koerper": neu})
    assert r.status_code == 200 and "Bis bald in Aeschi!" in r.json()["koerper"]
    # Tippfehler im Platzhalter wird abgefangen
    r = client.put(f"/email-vorlagen/{de['id']}", json={"betreff": "Hallo {{gastNmae}}", "koerper": neu})
    assert r.status_code == 400 and "gastNmae" in r.json()["detail"]
    # Änderung bleibt beim erneuten Ergänzen der Startvorlagen erhalten
    assert "Bis bald in Aeschi!" in client.get("/email-vorlagen").json()[0]["koerper"]


def test_vorschau_mit_beispieldaten(client):
    client.put("/einstellungen/betrieb", json=BETRIEB)
    fr = client.get("/email-vorlagen").json()[1]
    v = client.post("/email-vorlagen/vorschau", json={"betreff": fr["betreff"], "koerper": fr["koerper"], "sprache": "fr"}).json()
    assert v["betreff"].startswith("Votre réservation du 2 juillet 2027 au 5 juillet 2027")
    assert "caravane" in v["text"] and "CHF 120.00" in v["text"] and "31 mars 2027" in v["text"]
    assert v["unbekannte_platzhalter"] == [] and v["warnungen"] == []


def test_antwort_vorbereiten_englisch_ohne_frist_ohne_twint(client):
    client.put("/einstellungen/betrieb", json=BETRIEB)
    a = _anfrage(client)
    e = client.post(f"/reservationsanfragen/{a['id']}/antwort/vorbereiten", json={"sprache": "en", "betrag": "150"}).json()
    assert e["empfaenger"] == "mia@example.com"
    assert e["betreff"] == "Your reservation from 2 July 2027 to 5 July 2027 – Panorama-Camping Aeschi"
    t = e["text"]
    assert t.startswith("Dear Mia Beispiel,")
    assert "Departure: 5 July 2027 (3 nights)" in t and "Pitch: caravan" in t and "Guests: 3 adults\n" in t
    assert "deposit of CHF 150.00" in t and "IBAN CH00 0000 0000 0000 0000 0" in t and "BIC TESTCH22" in t
    assert "Please make the payment by" not in t and "TWINT" not in t
    assert t.index("Kind regards\nMuster Camping") < t.index("Check-in 14.00")  # Signatur vor Infoblock
    assert "{{" not in t and "\n\n\n" not in t
    assert e["warnungen"] == []


def test_antwort_mit_frist_twint_und_tausendertrennzeichen(client):
    client.put("/einstellungen/betrieb", json={**BETRIEB, "twint": "079 000 00 00"})
    a = _anfrage(client, sprache="de")
    t = client.post(f"/reservationsanfragen/{a['id']}/antwort/vorbereiten",
                    json={"sprache": "de", "betrag": "1250.5", "zahlungsfrist": "2027-03-31"}).json()["text"]
    assert "Anzahlung von CHF 1'250.50" in t
    assert "Bitte überweisen Sie den Betrag bis 31. März 2027." in t
    assert "per TWINT an 079 000 00 00" in t
    assert "Abreise: 5. Juli 2027 (3 Nächte)" in t and "Stellplatz: Wohnwagen" in t


def test_warnung_wenn_betriebsangaben_fehlen(client):
    a = _anfrage(client)
    e = client.post(f"/reservationsanfragen/{a['id']}/antwort/vorbereiten", json={"sprache": "de", "betrag": "50"}).json()
    assert e["warnungen"] and "IBAN" in e["warnungen"][0] and "Signatur" in e["warnungen"][0]


def test_regeln_vorbereiten(client):
    unvollstaendig = _anfrage(client, stellplatz_typ=None)
    assert client.post(f"/reservationsanfragen/{unvollstaendig['id']}/antwort/vorbereiten",
                       json={"sprache": "de", "betrag": "50"}).status_code == 400
    a = _anfrage(client)
    assert client.post(f"/reservationsanfragen/{a['id']}/antwort/vorbereiten", json={"sprache": "de", "betrag": "0"}).status_code == 422
    assert client.post(f"/reservationsanfragen/{a['id']}/antwort/vorbereiten", json={"sprache": "es", "betrag": "50"}).status_code == 422


def test_als_gesendet_markieren_protokolliert_und_setzt_status(client):
    client.put("/einstellungen/betrieb", json=BETRIEB)
    a = _anfrage(client)
    e = client.post(f"/reservationsanfragen/{a['id']}/antwort/vorbereiten", json={"sprache": "en", "betrag": "150"}).json()
    angepasst = e["text"].replace("Dear Mia Beispiel,", "Dear Mia,")
    r = client.post(f"/reservationsanfragen/{a['id']}/antwort/gesendet",
                    json={"vorlage_id": e["vorlage_id"], "betreff": e["betreff"], "text": angepasst})
    assert r.status_code == 200 and r.json()["status"] == "erstantwort_gesendet"
    mails = client.get(f"/reservationsanfragen/{a['id']}/mails").json()
    assert len(mails) == 1 and mails[0]["koerper_final"].startswith("Dear Mia,")
    assert mails[0]["empfaenger"] == "mia@example.com"


def test_datum_und_betrag_formatierung():
    assert am.datum_text(date(2027, 7, 2), "de") == "2. Juli 2027"
    assert am.datum_text(date(2027, 8, 1), "it") == "1 agosto 2027"
    assert am.betrag_text(Decimal("80")) == "CHF 80.00"


def test_personen_einzahl_mehrzahl():
    assert am.personen_text(2, 1, "de") == "2 Erwachsene, 1 Kind"
    assert am.personen_text(1, 0, "de") == "1 Erwachsene/r"
    assert am.personen_text(3, 2, "fr") == "3 adultes, 2 enfants"
    assert am.personen_text(1, 1, "it") == "1 adulto, 1 bambino"
    assert am.personen_text(3, 0, "en") == "3 adults"
