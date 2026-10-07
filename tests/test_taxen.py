"""Tests für Kurtaxe und Beherbergungsabgabe (nur Personen ab 16 Jahren, je Nacht)."""
from datetime import date
from decimal import Decimal

import pytest

from app.models import (
    Artikel, ArtikelPreis, Aufenthalt, Buchung, Campingplatz, Gast, Mwstsatz, Stellplatz, Taxensatz,
)
from app.services.taxen import alter_am, berechne_taxen


def _saetze():
    return [
        Taxensatz(typ="kurtaxe_gemeinde", gueltig_ab=date(2026, 1, 1), gueltig_bis=None,
                  altersgruppe_von=16, altersgruppe_bis=120,
                  betrag_pro_nacht=Decimal("3.50"), gemeinde_oder_kanton="Aeschi"),
        Taxensatz(typ="kurtaxe_gemeinde", gueltig_ab=date(2026, 1, 1), gueltig_bis=None,
                  altersgruppe_von=0, altersgruppe_bis=15,
                  betrag_pro_nacht=Decimal("0.00"), gemeinde_oder_kanton="Aeschi"),
        Taxensatz(typ="beherbergungsabgabe_kanton", gueltig_ab=date(2026, 1, 1), gueltig_bis=None,
                  altersgruppe_von=16, altersgruppe_bis=120,
                  betrag_pro_nacht=Decimal("1.00"), gemeinde_oder_kanton="Bern"),
    ]


def _aufenthalt(geburtsdatum, ankunft=date(2026, 7, 10), abreise=date(2026, 7, 15), taxpflichtig=True):
    gast = Gast(vorname="Test", nachname="Gast", geburtsdatum=geburtsdatum)
    return Aufenthalt(gast=gast, ankunft=ankunft, abreise=abreise, taxpflichtig=taxpflichtig)


def _betraege(ergebnis):
    return {p.typ: (p.personennaechte, p.betrag) for p in ergebnis.positionen}


def test_alter_am_stichtag():
    assert alter_am(date(2010, 7, 12), date(2026, 7, 11)) == 15
    assert alter_am(date(2010, 7, 12), date(2026, 7, 12)) == 16


def test_erwachsener_zahlt_beide_abgaben_je_nacht():
    e = berechne_taxen([_aufenthalt(date(1980, 1, 1))], _saetze())
    assert _betraege(e) == {
        "kurtaxe_gemeinde": (5, Decimal("17.50")),
        "beherbergungsabgabe_kanton": (5, Decimal("5.00")),
    }
    assert e.total == Decimal("22.50")
    assert e.warnungen == []


def test_kind_unter_16_zahlt_nichts():
    assert berechne_taxen([_aufenthalt(date(2016, 3, 1))], _saetze()).positionen == []


def test_familie_zwei_erwachsene_zwei_kinder_sieben_naechte():
    gaeste = [_aufenthalt(g, abreise=date(2026, 7, 17)) for g in
              (date(1985, 5, 5), date(1986, 6, 6), date(2014, 1, 1), date(2018, 1, 1))]
    e = berechne_taxen(gaeste, _saetze())
    assert _betraege(e) == {
        "kurtaxe_gemeinde": (14, Decimal("49.00")),
        "beherbergungsabgabe_kanton": (14, Decimal("14.00")),
    }
    assert e.total == Decimal("63.00")


def test_16_geburtstag_waehrend_des_aufenthalts_zaehlt_ab_dem_geburtstag():
    # 10./11.7. noch 15 Jahre, Nächte ab 12.7. mit 16
    e = berechne_taxen([_aufenthalt(date(2010, 7, 12), date(2026, 7, 10), date(2026, 7, 14))], _saetze())
    assert _betraege(e)["kurtaxe_gemeinde"] == (2, Decimal("7.00"))
    assert _betraege(e)["beherbergungsabgabe_kanton"] == (2, Decimal("2.00"))


def test_ohne_steuerrechtlichen_wohnsitz_nur_kurtaxe_entfaellt():
    e = berechne_taxen([_aufenthalt(date(1980, 1, 1), taxpflichtig=False)], _saetze())
    assert list(_betraege(e)) == ["beherbergungsabgabe_kanton"]


def test_fehlendes_geburtsdatum_wird_als_erwachsen_gerechnet_und_gemeldet():
    e = berechne_taxen([_aufenthalt(None)], _saetze())
    assert e.total == Decimal("22.50")
    assert "Geburtsdatum fehlt" in e.warnungen[0]


def test_satzaenderung_mitten_im_aufenthalt():
    saetze = _saetze()
    saetze[0].gueltig_bis = date(2026, 7, 11)
    saetze.append(Taxensatz(typ="kurtaxe_gemeinde", gueltig_ab=date(2026, 7, 12), gueltig_bis=None,
                            altersgruppe_von=16, altersgruppe_bis=120,
                            betrag_pro_nacht=Decimal("4.00"), gemeinde_oder_kanton="Aeschi"))
    e = berechne_taxen([_aufenthalt(date(1980, 1, 1), abreise=date(2026, 7, 14))], saetze)
    kurtaxe = [p for p in e.positionen if p.typ == "kurtaxe_gemeinde"]
    assert [(p.personennaechte, p.einzelpreis) for p in kurtaxe] == [(2, Decimal("3.50")), (2, Decimal("4.00"))]


@pytest.fixture
def buchung_mit_gaesten(db):
    ausgenommen = Mwstsatz(code="AUSGENOMMEN", bezeichnung="Ausgenommen", satz_prozent=Decimal("0"),
                           gueltig_ab=date(2000, 1, 1))
    normal = Mwstsatz(code="BEHERBERGUNG", bezeichnung="Beherbergung", satz_prozent=Decimal("3.8"),
                      gueltig_ab=date(2024, 1, 1))
    db.add_all([ausgenommen, normal])
    db.flush()
    taxen = [Artikel(code=c, bezeichnung=b, kategorie="taxe", einheit="pro_nacht", mwstsatz_id=ausgenommen.id)
             for c, b in (("KURTAXE", "Kurtaxe"), ("BEHERBERGUNGSABGABE", "Beherbergungsabgabe"))]
    erwachsene = Artikel(code="ERWACHSENE", bezeichnung="Erwachsene", kategorie="person",
                         einheit="pro_person_nacht", mwstsatz_id=normal.id)
    db.add_all([*taxen, erwachsene])
    db.add_all(_saetze())
    db.flush()
    db.add(ArtikelPreis(artikel_id=erwachsene.id, saison_id=None, preis=Decimal("8.00")))

    camping = Campingplatz(name="Camping Aeschi")
    db.add(camping)
    db.flush()
    platz = Stellplatz(campingplatz_id=camping.id, bezeichnung="A1", typ="zeltwiese")
    papa = Gast(vorname="Papa", nachname="Muster", geburtsdatum=date(1980, 1, 1))
    kind = Gast(vorname="Kind", nachname="Muster", geburtsdatum=date(2016, 1, 1))
    db.add_all([platz, papa, kind])
    db.flush()
    buchung = Buchung(stellplatz_id=platz.id, von=date(2026, 7, 10), bis=date(2026, 7, 15), hauptgast_id=papa.id)
    db.add(buchung)
    db.flush()
    for g in (papa, kind):
        db.add(Aufenthalt(buchung_id=buchung.id, gast_id=g.id, ankunft=date(2026, 7, 10), abreise=date(2026, 7, 15)))
    db.commit()
    return buchung, erwachsene


def test_vorschau_endpoint(client, buchung_mit_gaesten):
    buchung, _ = buchung_mit_gaesten
    daten = client.get("/rechnungen/taxen-vorschau", params={"buchung_id": str(buchung.id)}).json()
    assert daten["total"] == 22.5
    assert [p["bezeichnung"] for p in daten["positionen"]] == ["Kurtaxe Aeschi", "Beherbergungsabgabe Kanton Bern"]


def test_rechnung_enthaelt_taxen_automatisch(client, buchung_mit_gaesten):
    buchung, erwachsene = buchung_mit_gaesten
    antwort = client.post(
        "/rechnungen", params={"buchung_id": str(buchung.id)},
        json=[{"artikel_id": str(erwachsene.id), "menge": 5}],
    )
    assert antwort.status_code == 201
    rechnung = antwort.json()
    assert len(rechnung["positionen"]) == 3
    assert rechnung["gesamtbetrag"] == 40.0 + 22.5
    taxen = [p for p in rechnung["positionen"] if p["mwstsatz_prozent"] == 0]
    assert sorted(p["betrag"] for p in taxen) == [5.0, 17.5]
    assert all(p["mwst_betrag"] == 0 for p in taxen)


def test_rechnung_ohne_automatische_taxen(client, buchung_mit_gaesten):
    buchung, erwachsene = buchung_mit_gaesten
    antwort = client.post(
        "/rechnungen", params={"buchung_id": str(buchung.id), "mit_taxen": "false"},
        json=[{"artikel_id": str(erwachsene.id), "menge": 5}],
    )
    assert len(antwort.json()["positionen"]) == 1
