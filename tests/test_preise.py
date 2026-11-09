"""Tests: Saisons je Jahr, Preise zentral pflegen, Preise der Leistungen eines Aufenthalts."""
from datetime import date

import pytest

from app.models.buchung import Aufenthalt, Buchung, Gast
from app.seed import grunddaten_einspielen
from app.services import leistungen as lst


@pytest.fixture
def grunddaten(db):
    grunddaten_einspielen(db)
    db.commit()


def _aufenthalt(db, typ, von, bis, e=2, k=0, kk=0):
    g = Gast(vorname="Test", nachname="Preis", nationalitaet="CH")
    db.add(g)
    db.flush()
    b = Buchung(stellplatz_typ=typ, von=von, bis=bis, anzahl_erwachsene=e, anzahl_kinder=k, anzahl_kleinkinder=kk,
                status="eingecheckt", hauptgast_id=g.id)
    b.leistungen = lst.grundzeilen(b)
    db.add(b)
    db.flush()
    db.add(Aufenthalt(buchung_id=b.id, gast_id=g.id, ankunft=von, abreise=bis))
    db.commit()
    return str(b.id)


def _preise(d):
    return {z["bezeichnung"]: z["betrag"] for z in d["preise"]["zeilen"]}


def test_preisliste_saisons_2027(client, grunddaten):
    d = client.get("/preise/2027").json()
    assert [(s["typ"], s["gueltig_ab"], s["gueltig_bis"]) for s in d["saisons"]] == [
        ("vorsaison", "2027-05-01", "2027-06-30"), ("hauptsaison", "2027-07-01", "2027-08-31"),
        ("nachsaison", "2027-09-01", "2027-09-30")]
    a = {x["code"]: x for x in d["artikel"]}
    assert a["ERWACHSENE"]["preise"] == {"vorsaison": 7.0, "hauptsaison": 8.0, "nachsaison": 7.0}
    assert a["STROM"]["saisonal"] is False and a["STROM"]["preise"] == {"ganzjaehrig": 4.0}
    assert a["CAMPER"]["mwst_prozent"] == 3.8 and "KURTAXE" not in a
    assert d["jahre"] == [2026, 2027]


def test_preise_und_saisondaten_aendern(client, grunddaten):
    a = {x["code"]: x for x in client.get("/preise/2027").json()["artikel"]}
    r = client.put("/preise/2027", json={
        "saisons": [{"typ": "nachsaison", "gueltig_ab": "2027-09-01", "gueltig_bis": "2027-10-15"}],
        "preise": [{"artikel_id": a["ERWACHSENE"]["id"], "saison": "hauptsaison", "preis": "8.50"},
                   {"artikel_id": a["STROM"]["id"], "saison": "ganzjaehrig", "preis": "4.50"}]})
    assert r.status_code == 200, r.text
    d = r.json()
    a = {x["code"]: x for x in d["artikel"]}
    assert a["ERWACHSENE"]["preise"]["hauptsaison"] == 8.5 and a["ERWACHSENE"]["preise"]["vorsaison"] == 7.0
    assert a["STROM"]["preise"]["ganzjaehrig"] == 4.5
    assert d["saisons"][2]["gueltig_bis"] == "2027-10-15"
    # 2026 bleibt unverändert
    assert {x["code"]: x for x in client.get("/preise/2026").json()["artikel"]}["ERWACHSENE"]["preise"]["hauptsaison"] == 8.0
    # Überschneidung und falsches Jahr
    assert client.put("/preise/2027", json={"saisons": [
        {"typ": "vorsaison", "gueltig_ab": "2027-05-01", "gueltig_bis": "2027-07-05"}]}).status_code == 400
    assert client.put("/preise/2027", json={"saisons": [
        {"typ": "vorsaison", "gueltig_ab": "2026-05-01", "gueltig_bis": "2027-06-30"}]}).status_code == 400
    assert client.put("/preise/2027", json={"preise": [
        {"artikel_id": a["CAMPER"]["id"], "saison": "hauptsaison", "preis": "-1"}]}).status_code == 422


def test_jahr_uebernehmen(client, grunddaten):
    a = {x["code"]: x for x in client.get("/preise/2027").json()["artikel"]}
    client.put("/preise/2027", json={"preise": [{"artikel_id": a["CAMPER"]["id"], "saison": "hauptsaison", "preis": "19"}]})
    r = client.post("/preise/2028/uebernehmen", json={"von_jahr": 2027})
    assert r.status_code == 201, r.text
    d = r.json()
    assert [s["bezeichnung"] for s in d["saisons"]] == ["Vorsaison 2028", "Hauptsaison 2028", "Nachsaison 2028"]
    assert {x["code"]: x for x in d["artikel"]}["CAMPER"]["preise"]["hauptsaison"] == 19.0
    assert client.post("/preise/2028/uebernehmen", json={"von_jahr": 2027}).status_code == 400
    assert client.post("/preise/2030/uebernehmen", json={"von_jahr": 2029}).status_code == 400


def test_aufenthalt_preise_ueber_saisonwechsel_mit_taxen(client, db, grunddaten):
    bid = _aufenthalt(db, "camper", date(2027, 6, 30), date(2027, 7, 2), e=2, k=1, kk=1)
    client.post(f"/aufenthalte/{bid}/leistungen", json={"art": "wassertank", "von": "2027-06-30"})
    d = client.get(f"/aufenthalte/{bid}/leistungen").json()
    p = _preise(d)
    assert p["Erwachsene (ab 16)"] == "30.00"    # 2 × (7.00 Vorsaison + 8.00 Hauptsaison)
    assert p["Kinder (6–15)"] == "7.40"          # 3.40 + 4.00
    assert p["Kleinkinder (0–5)"] == "0.00"
    assert p["Camper"] == "34.00" and p["Umweltabgabe"] == "2.00"
    wt = next(z for z in d["preise"]["zeilen"] if z["bezeichnung"] == "Wassertankfüllung")
    assert wt["betrag"] == "0.00" and wt["hinweis"] == "ab 2 Nächten inbegriffen"
    erw = next(z for z in d["preise"]["zeilen"] if z["bezeichnung"] == "Erwachsene (ab 16)")
    assert erw["einzelpreise"] == ["7.00", "8.00"] and erw["einzelpreis"] is None
    assert d["preise"]["total"] == "73.40" and d["preise"]["fehlende_preise"] is False
    assert d["preise"]["total_mit_taxen"] == "91.40"   # + Kurtaxe 14.00 + Beherbergungsabgabe 4.00
    assert d["preise"]["mwst_total"] != "0.00"


def test_wassertank_bei_einer_nacht_und_ausserhalb_saison(client, db, grunddaten):
    bid = _aufenthalt(db, "zeltwiese", date(2027, 8, 10), date(2027, 8, 11), e=1)
    client.post(f"/aufenthalte/{bid}/leistungen", json={"art": "wassertank", "von": "2027-08-10"})
    assert _preise(client.get(f"/aufenthalte/{bid}/leistungen").json())["Wassertankfüllung"] == "5.00"
    winter = _aufenthalt(db, "camper", date(2026, 11, 10), date(2026, 11, 12), e=2)
    d = client.get(f"/aufenthalte/{winter}/leistungen").json()
    assert d["preise"]["fehlende_preise"] is True
    erw = next(z for z in d["preise"]["zeilen"] if z["bezeichnung"] == "Erwachsene (ab 16)")
    assert (erw["betrag"], erw["hinweis"]) == ("0.00", "kein Preis hinterlegt")
    teil = _aufenthalt(db, "camper", date(2027, 9, 29), date(2027, 10, 2), e=1)
    erw = next(z for z in client.get(f"/aufenthalte/{teil}/leistungen").json()["preise"]["zeilen"]
               if z["bezeichnung"] == "Erwachsene (ab 16)")
    assert erw["betrag"] == "14.00" and erw["hinweis"] == "1 von 3 Nächten ohne Preis (ausserhalb der Saison)"


def test_zwaergli_mit_zwei_personen_inbegriffen(client, db, grunddaten):
    bid = _aufenthalt(db, "zwaergli", date(2027, 7, 10), date(2027, 7, 12), e=3)
    d = client.get(f"/aufenthalte/{bid}/leistungen").json()
    p = _preise(d)
    assert p["Zwärgli"] == "80.00" and p["Erwachsene (ab 16)"] == "48.00" and "Umweltabgabe" not in p
    assert [(a["bezeichnung"], a["betrag"]) for a in d["preise"]["abzuege"]] == [
        ("Inbegriffen im Zwärgli (2 Personen je Nacht)", "-32.00")]
    assert d["preise"]["total"] == "96.00"


# --- unverbindlicher Preis pro Nacht in der Bestätigung --------------------------

from app.models.reservation import Reservationsanfrage  # noqa: E402
from app.services import richtpreis  # noqa: E402


def _anfrage(db, typ, von, bis, e=2, k=0, kk=0):
    a = Reservationsanfrage(quelle="manuell", eingangs_datum=date(2026, 10, 1), sprache="de", gast_name="Preis Test",
                            gast_email="preis@example.com", gewuenscht_von=von, gewuenscht_bis=bis, stellplatz_typ=typ,
                            anzahl_erwachsene=e, anzahl_kinder=k, anzahl_kleinkinder=kk, status="bezahlt_akzeptiert")
    db.add(a)
    db.commit()
    return a


def test_richtpreis_hauptsaison_mit_kleinkind(db, grunddaten):
    a = _anfrage(db, "wohnwagen", date(2027, 7, 2), date(2027, 7, 5), e=2, k=1, kk=1)
    text, warnung = richtpreis.text(db, a, "de")
    assert warnung is None
    assert text == ("Unverbindlicher Preis pro Nacht (Hauptsaison): CHF 47.00\n"
                    "Wohnwagen CHF 17.00, 2 Erwachsene à CHF 8.00, 1 Kind à CHF 4.00, Umweltabgabe CHF 1.00, "
                    "Kurtaxe und Beherbergungsabgabe CHF 9.00, 1 Kleinkind gratis")
    fr, _ = richtpreis.text(db, a, "fr")
    assert fr.startswith("Prix indicatif par nuit (haute saison) : CHF 47.00") or fr.startswith("Prix indicatif par nuit (haute saison): CHF 47.00")


def test_richtpreis_ueber_saisonwechsel_und_zwaergli(db, grunddaten):
    a = _anfrage(db, "zeltwiese", date(2027, 6, 29), date(2027, 7, 2), e=2, k=1)
    text, _ = richtpreis.text(db, a, "de")
    teile = text.split("\n\n")
    assert teile[0].startswith("Unverbindlicher Preis pro Nacht (Vorsaison, 2 Nächte): CHF 39.40")
    assert teile[1].startswith("Unverbindlicher Preis pro Nacht (Hauptsaison, 1 Nacht): CHF 44.00")
    z = _anfrage(db, "zwaergli", date(2027, 8, 1), date(2027, 8, 3), e=3)
    text, _ = richtpreis.text(db, z, "de")
    assert text == ("Unverbindlicher Preis pro Nacht (Hauptsaison): CHF 61.50\n"
                    "Zwärgli für 2 Personen CHF 40.00, 1 weitere Person à CHF 8.00, Kurtaxe und Beherbergungsabgabe CHF 13.50")
    winter = _anfrage(db, "camper", date(2026, 11, 20), date(2026, 11, 22))
    text, warnung = richtpreis.text(db, winter, "de")
    assert text == "" and "20.11.2026" in warnung


def test_bestaetigung_mit_preis_nur_bei_eingeschaltetem_modul(client, db, grunddaten):
    a = client.post("/reservationsanfragen", json={
        "quelle": "manuell", "eingangs_datum": "2026-10-01T10:00:00+02:00", "sprache": "de", "gast_name": "Mia Preis",
        "gast_email": "mia@example.com", "gewuenscht_von": "2027-07-02", "gewuenscht_bis": "2027-07-05",
        "stellplatz_typ": "camper", "anzahl_erwachsene": 2}).json()
    client.post(f"/reservationsanfragen/{a['id']}/zahlung-bestaetigen", json={})
    vorbereiten = lambda: client.post(f"/reservationsanfragen/{a['id']}/antwort/vorbereiten",  # noqa: E731
                                      json={"typ": "bestaetigung_definitiv", "sprache": "de"}).json()
    ohne = vorbereiten()
    assert "Unverbindlicher Preis" not in ohne["text"] and not any("Preis" in w for w in ohne["warnungen"])
    client.put("/einstellungen/module/artikel", json={"aktiv": True})
    mit = vorbereiten()
    assert "Unverbindlicher Preis pro Nacht (Hauptsaison): CHF 44.00" in mit["text"]   # 18 + 2×8 + 1 + 2×4.50
    assert mit["text"].index("Personen:") < mit["text"].index("Unverbindlicher Preis") < mit["text"].index("Wir freuen")


def test_alte_bestaetigungsvorlage_erhaelt_platzhalter(db):
    from app.models.kommunikation import EmailVorlage
    from app.services import antwortmail as am
    betreff, koerper = am.STARTVORLAGEN_BESTAETIGUNG["de"]
    alt = koerper.replace("\n\n{{preisProNacht}}", "")
    db.add(EmailVorlage(typ=am.TYP_BESTAETIGUNG, sprache="de", betreff=betreff, koerper=alt, aktiv=True))
    db.add(EmailVorlage(typ=am.TYP_BESTAETIGUNG, sprache="fr", betreff="x", koerper="Eigener Text", aktiv=True))
    db.commit()
    am.startvorlagen_ergaenzen(db)
    vorlagen = {v.sprache: v.koerper for v in db.query(EmailVorlage).filter_by(typ=am.TYP_BESTAETIGUNG)}
    assert "{{preisProNacht}}" in vorlagen["de"] and vorlagen["fr"] == "Eigener Text"
