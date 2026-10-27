"""Tests: Reservationen bearbeiten, Status, Belegung nach Typ, Modul-Schalter."""
from datetime import date


def _anfrage(client, **felder):
    daten = {
        "quelle": "manuell",
        "eingangs_datum": "2026-06-01T10:00:00+00:00",
        "gast_name": "Anna Muster",
        "gast_email": "anna@example.ch",
        "gewuenscht_von": "2026-07-10",
        "gewuenscht_bis": "2026-07-13",
        "stellplatz_typ": "zeltwiese",
        "anzahl_erwachsene": 2,
        "anzahl_kinder": 1,
    }
    daten.update(felder)
    antwort = client.post("/reservationsanfragen", json=daten)
    assert antwort.status_code == 201, antwort.text
    return antwort.json()


# --- Reservationen ---------------------------------------------------------

def test_unvollstaendige_anfrage_ohne_zeitraum_ergaenzen(client):
    a = _anfrage(client, gewuenscht_von=None, gewuenscht_bis=None, stellplatz_typ=None)
    assert a["status"] == "unvollstaendig"
    assert "zeitraum" in a["fehlende_angaben"] and "stellplatz_typ" in a["fehlende_angaben"]

    neu = client.patch(f"/reservationsanfragen/{a['id']}", json={
        "gewuenscht_von": "2026-08-01", "gewuenscht_bis": "2026-08-05", "stellplatz_typ": "camper",
    }).json()
    assert neu["vollstaendig"] is True
    assert neu["status"] == "geprueft_vollstaendig"
    assert neu["fehlende_angaben"] is None


def test_detail_enthaelt_rohtext(client):
    a = _anfrage(client, rohtext="Guten Tag, wir möchten ...")
    assert client.get(f"/reservationsanfragen/{a['id']}").json()["rohtext"].startswith("Guten Tag")


def test_ungueltiger_stellplatz_typ_wird_abgelehnt(client):
    antwort = client.post("/reservationsanfragen", json={
        "quelle": "manuell", "eingangs_datum": "2026-06-01T10:00:00+00:00",
        "gast_name": "X", "gast_email": "x@example.ch", "stellplatz_typ": "schloss",
    })
    assert antwort.status_code == 422


def test_status_workflow_und_regeln(client):
    a = _anfrage(client)
    for status in ("erstantwort_gesendet", "zahlung_ausstehend", "bezahlt_akzeptiert"):
        r = client.post(f"/reservationsanfragen/{a['id']}/status", json={"status": status})
        assert r.status_code == 200 and r.json()["status"] == status

    # Änderung der Angaben setzt einen fortgeschrittenen Status nicht zurück
    r = client.patch(f"/reservationsanfragen/{a['id']}", json={"anzahl_kinder": 2}).json()
    assert r["status"] == "bezahlt_akzeptiert" and r["anzahl_kinder"] == 2

    # Unvollständige Anfrage darf nicht akzeptiert werden
    b = _anfrage(client, stellplatz_typ=None)
    r = client.post(f"/reservationsanfragen/{b['id']}/status", json={"status": "bezahlt_akzeptiert"})
    assert r.status_code == 400

    # Ablehnen geht immer; zurück in die Prüfung ergibt den Prüfstatus
    assert client.post(f"/reservationsanfragen/{b['id']}/status", json={"status": "abgelehnt"}).json()["status"] == "abgelehnt"
    assert client.post(f"/reservationsanfragen/{b['id']}/status", json={"status": "neu"}).json()["status"] == "unvollstaendig"

    assert client.post(f"/reservationsanfragen/{a['id']}/status", json={"status": "irgendwas"}).status_code == 422


# --- Belegung --------------------------------------------------------------

def test_belegung_nach_typ_mit_erwachsenen_und_kindern(client):
    a = _anfrage(client)  # Zelt 10.–13.7., 2E 1K (offen)
    b = _anfrage(client, gast_name="Ben", stellplatz_typ="wohnwagen",
                 gewuenscht_von="2026-07-12", gewuenscht_bis="2026-07-15", anzahl_erwachsene=3, anzahl_kinder=0)
    client.post(f"/reservationsanfragen/{b['id']}/status", json={"status": "bezahlt_akzeptiert"})
    c = _anfrage(client, gast_name="Clara", gewuenscht_von="2026-07-11", gewuenscht_bis="2026-07-12")
    client.post(f"/reservationsanfragen/{c['id']}/status", json={"status": "storniert"})
    _anfrage(client, gast_name="Ausserhalb", gewuenscht_von="2026-09-01", gewuenscht_bis="2026-09-03")

    bel = client.get("/belegung", params={"von": "2026-07-10", "bis": "2026-07-16"}).json()
    namen = [e["gast_name"] for e in bel["eintraege"]]
    assert namen == ["Anna Muster", "Ben"]  # storniert und ausserhalb fehlen

    anna = bel["eintraege"][0]
    assert (anna["naechte"], anna["erwachsene"], anna["kinder"], anna["akzeptiert"]) == (3, 2, 1, False)

    zelt = next(t for t in bel["nach_typ"] if t["stellplatz_typ"] == "zeltwiese")
    tage = {t["datum"]: t for t in zelt["tage"]}
    assert tage["2026-07-12"]["anzahl"] == 1 and tage["2026-07-12"]["erwachsene"] == 2
    assert tage["2026-07-13"]["anzahl"] == 0  # Abreisetag zählt nicht
    assert len(zelt["tage"]) == 7

    nur_akz = client.get("/belegung", params={"von": "2026-07-10", "bis": "2026-07-16", "status": "akzeptiert"}).json()
    assert [e["gast_name"] for e in nur_akz["eintraege"]] == ["Ben"]
    nur_offen = client.get("/belegung", params={"von": "2026-07-10", "bis": "2026-07-16", "status": "offen"}).json()
    assert [e["gast_name"] for e in nur_offen["eintraege"]] == ["Anna Muster"]


def test_belegung_zeitraum_wird_geprueft(client):
    assert client.get("/belegung", params={"von": "2026-07-10", "bis": "2026-07-01"}).status_code == 400
    assert client.get("/belegung", params={"von": "2026-01-01", "bis": "2027-12-31"}).status_code == 400


# --- Module ----------------------------------------------------------------

def test_module_standard_und_umschalten(client):
    module = {m["code"]: m for m in client.get("/einstellungen/module").json()}
    assert module["reservationen"]["aktiv"] and not module["reservationen"]["umschaltbar"]
    assert module["gaeste"]["aktiv"] and module["belegung"]["aktiv"]
    for aus in ("buchungen", "artikel", "rechnungen", "auswertungen", "hesta", "feratel"):
        assert module[aus]["aktiv"] is False and module[aus]["umschaltbar"] is True

    r = client.put("/einstellungen/module/hesta", json={"aktiv": True})
    assert {m["code"]: m["aktiv"] for m in r.json()}["hesta"] is True
    assert {m["code"]: m["aktiv"] for m in client.get("/einstellungen/module").json()}["hesta"] is True
    client.put("/einstellungen/module/hesta", json={"aktiv": False})
    assert {m["code"]: m["aktiv"] for m in client.get("/einstellungen/module").json()}["hesta"] is False

    assert client.put("/einstellungen/module/reservationen", json={"aktiv": False}).status_code == 400
    assert client.put("/einstellungen/module/gibtsnicht", json={"aktiv": True}).status_code == 404


def test_gaeste_suche_nach_vorname_und_ort(client):
    client.post("/gaeste", json={"vorname": "Hans", "nachname": "Zbinden", "ort": "Aeschi"})
    client.post("/gaeste", json={"vorname": "Ursula", "nachname": "Meier", "ort": "Thun"})
    assert [g["nachname"] for g in client.get("/gaeste", params={"suche": "hans"}).json()] == ["Zbinden"]
    assert [g["nachname"] for g in client.get("/gaeste", params={"suche": "thun"}).json()] == ["Meier"]
