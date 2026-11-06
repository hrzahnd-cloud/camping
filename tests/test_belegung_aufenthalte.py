"""Tests: Auslastung je Nacht, Meldung ab 45, Check-in, Nichterscheinen, Abreise, Löschen (fiktive Daten)."""
from datetime import date, timedelta

HEUTE = date.today()


def _anfrage(client, von, bis, typ="wohnwagen", name="Test Gast", akzeptieren=True, **felder):
    daten = {
        "quelle": "manuell", "eingangs_datum": "2026-10-01T10:00:00+02:00", "sprache": "de",
        "gast_name": name, "gast_email": "gast@example.com", "gewuenscht_von": str(von), "gewuenscht_bis": str(bis),
        "stellplatz_typ": typ, "anzahl_erwachsene": 2, "anzahl_kinder": 1,
    }
    daten.update(felder)
    a = client.post("/reservationsanfragen", json=daten).json()
    if akzeptieren:
        a = client.post(f"/reservationsanfragen/{a['id']}/zahlung-bestaetigen", json={"betrag": "50"}).json()
    return a


def test_auslastung_zaehlt_nur_akzeptierte_stellplaetze(client):
    client.put("/belegung/einstellungen", json={"belegung_plaetze": 5, "belegung_meldung_ab": 3})
    juli = date(2027, 7, 10)
    _anfrage(client, juli, juli + timedelta(days=3))
    _anfrage(client, juli, juli + timedelta(days=1), typ="camper")
    _anfrage(client, juli, juli + timedelta(days=2), typ="zwaergli")  # zählt nicht zu den Stellplätzen
    _anfrage(client, juli, juli + timedelta(days=2), akzeptieren=False)  # offen: zählt nicht
    b = client.get(f"/belegung?von={juli}&bis={juli + timedelta(days=3)}").json()
    assert (b["plaetze"], b["meldung_ab"]) == (5, 3)
    assert [(x["belegt"], x["stufe"]) for x in b["auslastung"]] == [(2, "normal"), (1, "normal"), (1, "normal"), (0, "normal")]
    # offene Anfrage erscheint trotzdem als Eintrag (schraffiert)
    assert len(b["eintraege"]) == 4


def test_meldung_ab_grenze_in_anfrage(client):
    client.put("/belegung/einstellungen", json={"belegung_plaetze": 4, "belegung_meldung_ab": 3})
    tag = date(2027, 7, 20)
    for i in range(2):
        _anfrage(client, tag, tag + timedelta(days=2), name=f"Belegt {i}")
    neu = _anfrage(client, tag + timedelta(days=1), tag + timedelta(days=4), akzeptieren=False, name="Neu")
    d = client.get(f"/reservationsanfragen/{neu['id']}").json()
    assert [(h["datum"], h["mit_dieser"], h["plaetze"]) for h in d["hohe_belegung"]] == [("2027-07-21", 3, 4)]
    # Zwärgli/Spycher: keine Meldung
    z = _anfrage(client, tag, tag + timedelta(days=2), typ="spycher", akzeptieren=False)
    assert client.get(f"/reservationsanfragen/{z['id']}").json()["hohe_belegung"] == []
    voll = client.get(f"/belegung?von={tag}&bis={tag}").json()["auslastung"][0]
    assert voll == {"datum": str(tag), "belegt": 2, "stufe": "normal"}


def test_einstellungen_pruefen(client):
    assert client.get("/belegung/einstellungen").json() == {"belegung_plaetze": 50, "belegung_meldung_ab": 45}
    assert client.put("/belegung/einstellungen", json={"belegung_plaetze": 50, "belegung_meldung_ab": 60}).status_code == 400


def test_checkin_aus_reservation_und_nicht_angereist(client):
    gestern = HEUTE - timedelta(days=1)
    a = _anfrage(client, gestern, HEUTE + timedelta(days=3), name="Lea Muster")
    b = _anfrage(client, gestern, HEUTE + timedelta(days=2), name="Max Fehlt")
    zukunft = _anfrage(client, HEUTE + timedelta(days=5), HEUTE + timedelta(days=7), name="Kommt Später")

    offen = client.get("/belegung/nicht-angereist").json()
    assert {x["gast_name"] for x in offen} == {"Lea Muster", "Max Fehlt"}

    # Check-in in der Zukunft nicht möglich
    r = client.post("/aufenthalte", json={"reservationsanfrage_id": zukunft["id"], "vorname": "Kommt", "nachname": "Später",
                                          "stellplatz_typ": "wohnwagen", "von": str(zukunft["gewuenscht_von"]),
                                          "bis": str(zukunft["gewuenscht_bis"])})
    assert r.status_code == 400

    r = client.post("/aufenthalte", json={
        "reservationsanfrage_id": a["id"], "vorname": "Lea", "nachname": "Muster", "land": "CH", "plz": "3000", "ort": "Bern",
        "stellplatz_typ": "wohnwagen", "platz": " 17 ", "von": str(gestern), "bis": str(HEUTE + timedelta(days=3)),
        "anzahl_erwachsene": 2, "anzahl_kinder": 1})
    assert r.status_code == 201, r.text
    auf = r.json()
    assert auf["status"] == "eingecheckt" and auf["platz"] == "17" and auf["email"] == "gast@example.com"
    d = client.get(f"/reservationsanfragen/{a['id']}").json()
    assert d["status"] == "angereist" and d["buchung_id"] == auf["buchung_id"]
    assert client.post(f"/reservationsanfragen/{a['id']}/status", json={"status": "storniert"}).status_code == 400

    # Belegung: Aufenthalt statt Reservation, nicht doppelt gezählt
    bel = client.get(f"/belegung?von={HEUTE}&bis={HEUTE}").json()
    arten = sorted((e["art"], e["gast_name"]) for e in bel["eintraege"])
    assert arten == [("aufenthalt", "Lea Muster"), ("reservation", "Max Fehlt")]
    assert bel["auslastung"][0]["belegt"] == 2

    # Max ist nicht gekommen -> Platz frei
    r = client.post(f"/reservationsanfragen/{b['id']}/nicht-erschienen")
    assert r.status_code == 200 and r.json()["status"] == "nicht_erschienen"
    assert client.get(f"/belegung?von={HEUTE}&bis={HEUTE}").json()["auslastung"][0]["belegt"] == 1
    assert client.get("/belegung/nicht-angereist").json() == []
    assert client.post(f"/reservationsanfragen/{zukunft['id']}/nicht-erschienen").status_code == 400

    # Abreise heute: Platz ab heute frei
    r = client.post(f"/aufenthalte/{auf['buchung_id']}/abreise", json={})
    assert r.json()["status"] == "ausgecheckt" and r.json()["bis"] == str(HEUTE)
    assert client.get(f"/belegung?von={HEUTE}&bis={HEUTE}").json()["auslastung"][0]["belegt"] == 0
    assert client.get(f"/belegung?von={gestern}&bis={gestern}").json()["auslastung"][0]["belegt"] == 1


def test_checkin_ohne_reservation_und_loeschen(client):
    r = client.post("/aufenthalte", json={"vorname": "Ohne", "nachname": "Anmeldung", "stellplatz_typ": "zeltwiese",
                                          "von": str(HEUTE), "bis": str(HEUTE + timedelta(days=1)), "anzahl_erwachsene": 1})
    assert r.status_code == 201 and r.json()["reservationsanfrage_id"] is None
    assert client.get(f"/belegung?von={HEUTE}&bis={HEUTE}").json()["auslastung"][0]["belegt"] == 1
    assert client.delete(f"/aufenthalte/{r.json()['buchung_id']}").status_code == 204
    assert client.get(f"/belegung?von={HEUTE}&bis={HEUTE}").json()["auslastung"][0]["belegt"] == 0
    r = client.post("/aufenthalte", json={"vorname": "X", "nachname": "Y", "stellplatz_typ": "zeltwiese",
                                          "von": str(HEUTE), "bis": str(HEUTE)})
    assert r.status_code == 400


def test_aufenthalt_loeschen_setzt_reservation_zurueck_und_anfrage_loeschen(client):
    a = _anfrage(client, HEUTE, HEUTE + timedelta(days=2), name="Ina Zurück")
    auf = client.post("/aufenthalte", json={"reservationsanfrage_id": a["id"], "vorname": "Ina", "nachname": "Zurück",
                                            "stellplatz_typ": "wohnwagen", "von": str(HEUTE),
                                            "bis": str(HEUTE + timedelta(days=2))}).json()
    assert client.delete(f"/reservationsanfragen/{a['id']}").status_code == 400  # Aufenthalt vorhanden
    client.delete(f"/aufenthalte/{auf['buchung_id']}")
    assert client.get(f"/reservationsanfragen/{a['id']}").json()["status"] == "bezahlt_akzeptiert"
    assert client.delete(f"/reservationsanfragen/{a['id']}").status_code == 204
    assert client.get(f"/reservationsanfragen/{a['id']}").status_code == 404
