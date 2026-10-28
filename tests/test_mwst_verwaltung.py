"""Tests: MWST-Sätze je Jahr hinterlegen und am Leistungsdatum anwenden."""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models import Artikel, Mwstsatz
from app.services import mwst
from tests.test_taxen import buchung_mit_gaesten  # noqa: F401  (Fixture)


@pytest.fixture
def saetze(db):
    beherbergung = Mwstsatz(code="BEHERBERGUNG", bezeichnung="Sondersatz Beherbergung",
                            satz_prozent=Decimal("3.8"), gueltig_ab=date(2024, 1, 1))
    normal = Mwstsatz(code="NORMAL", bezeichnung="Normalsatz", satz_prozent=Decimal("8.1"), gueltig_ab=date(2024, 1, 1))
    db.add_all([beherbergung, normal])
    db.flush()
    zelt = Artikel(code="ZELT", bezeichnung="Zelt", kategorie="stellplatz", einheit="pro_nacht", mwstsatz_id=beherbergung.id)
    db.add(zelt)
    db.commit()
    return zelt


def test_neuer_satz_gilt_ab_datum_und_schliesst_vorherigen(db, saetze):
    zelt = saetze
    mwst.neuen_satz_hinterlegen(db, "BEHERBERGUNG", Decimal("4.0"), date(2028, 1, 1))
    assert mwst.prozent_fuer_artikel(db, zelt, date(2027, 12, 31)) == Decimal("3.8")
    assert mwst.prozent_fuer_artikel(db, zelt, date(2028, 1, 1)) == Decimal("4.0")
    alt = mwst.satz_am(db, "BEHERBERGUNG", date(2025, 6, 1))
    assert alt.gueltig_bis == date(2027, 12, 31)


def test_neuer_satz_muss_nach_dem_letzten_beginnen(db, saetze):
    with pytest.raises(ValueError):
        mwst.neuen_satz_hinterlegen(db, "BEHERBERGUNG", Decimal("4.0"), date(2023, 1, 1))
    with pytest.raises(ValueError):
        mwst.neuen_satz_hinterlegen(db, "UNBEKANNT", Decimal("4.0"), date(2028, 1, 1))


def test_api_auflisten_hinterlegen_und_korrigieren(client, saetze):
    liste = client.get("/mwst-saetze").json()
    assert [c["code"] for c in liste] == ["BEHERBERGUNG", "NORMAL"]
    assert liste[0]["aktueller_satz"] == "3.80" and liste[0]["saetze"][0]["aktuell"] is True

    neu = client.post("/mwst-saetze/BEHERBERGUNG", json={"satz_prozent": "4.0", "gueltig_ab": "2028-01-01"})
    assert neu.status_code == 201
    beh = neu.json()[0]
    assert beh["aktueller_satz"] == "3.80"  # gilt erst ab 2028
    assert [(s["gueltig_ab"], s["gueltig_bis"], s["zukuenftig"]) for s in beh["saetze"]] == [
        ("2028-01-01", None, True), ("2024-01-01", "2027-12-31", False)]

    # Fehleingabe korrigieren: zukünftiger Satz kann entfernt werden, der alte ist wieder offen
    r = client.delete(f"/mwst-saetze/{beh['saetze'][0]['id']}")
    assert r.status_code == 200
    assert [(s["gueltig_ab"], s["gueltig_bis"]) for s in r.json()[0]["saetze"]] == [("2024-01-01", None)]
    # der gültige Satz kann nicht entfernt werden
    assert client.delete(f"/mwst-saetze/{beh['saetze'][1]['id']}").status_code == 400
    assert client.post("/mwst-saetze/BEHERBERGUNG", json={"satz_prozent": "120", "gueltig_ab": "2028-01-01"}).status_code == 422


def test_rechnung_verwendet_satz_am_leistungsdatum(client, db, buchung_mit_gaesten):  # noqa: F811
    buchung, erwachsene = buchung_mit_gaesten
    # Neuer Satz ab heute: Rechnungen ab heute rechnen mit 4.0 %, obwohl der Artikel
    # noch auf den alten Datensatz verweist.
    mwst.neuen_satz_hinterlegen(db, "BEHERBERGUNG", Decimal("4.0"), date.today())
    r = client.post("/rechnungen", params={"buchung_id": str(buchung.id)},
                    json=[{"artikel_id": str(erwachsene.id), "menge": 5}]).json()
    pos = next(p for p in r["positionen"] if p["mwstsatz_prozent"] != 0)
    assert pos["mwstsatz_prozent"] == 4.0


def test_artikelpreis_zeigt_gueltigen_satz(client, saetze, db):
    from app.models import ArtikelPreis
    db.add(ArtikelPreis(artikel_id=saetze.id, saison_id=None, preis=Decimal("14.00")))
    db.commit()
    mwst.neuen_satz_hinterlegen(db, "BEHERBERGUNG", Decimal("4.0"), date.today() + timedelta(days=400))
    heute = client.get(f"/artikel/{saetze.id}/preis", params={"stichtag": date.today().isoformat()}).json()
    spaeter = client.get(f"/artikel/{saetze.id}/preis", params={"stichtag": (date.today() + timedelta(days=401)).isoformat()}).json()
    assert heute["mwstsatz_prozent"] == 3.8 and spaeter["mwstsatz_prozent"] == 4.0
