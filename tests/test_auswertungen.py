"""Tests: Einnahmen/MWST vereinnahmt, Übernachtungen/Taxen je Monat, Saison mit Excel/PDF."""
from datetime import date, datetime, timezone
from decimal import Decimal
from io import BytesIO

from openpyxl import load_workbook

from app.models.reservation import Reservationsanfrage, Zahlung
from tests.test_rechnungen import _aufenthalt, grunddaten  # noqa: F401

HEUTE = date.today()


def _anzahlung_ohne_aufenthalt(db, betrag, tag):
    a = Reservationsanfrage(quelle="manuell", eingangs_datum=datetime(2026, 7, 1, tzinfo=timezone.utc), sprache="de",
                            gast_name="Nora Nichtda", gast_email="nora@example.com", gewuenscht_von=date(2026, 8, 20),
                            gewuenscht_bis=date(2026, 8, 22), stellplatz_typ="zeltwiese", anzahl_erwachsene=2,
                            status="nicht_erschienen")
    db.add(a)
    db.flush()
    db.add(Zahlung(bezug_typ="reservationsanfrage", bezug_id=a.id, betrag=Decimal(betrag), zahlungsart="bankueberweisung",
                   status="eingegangen", eingegangen_am=datetime.combine(tag, datetime.min.time(), tzinfo=timezone.utc)))
    db.commit()


def test_einnahmen_vereinnahmt_aufgeteilt_nach_rechnung(client, db, grunddaten):  # noqa: F811
    bid = _aufenthalt(db, anzahlung="50")          # Anzahlung am 5.10.2026, Aufenthalt 30.6.–2.7.2026, Total 91.40
    client.post(f"/rechnungen/aus-aufenthalt/{bid}", json={"zahlungsart": "twint"})   # Rest 41.40 heute
    _anzahlung_ohne_aufenthalt(db, "100", date(2026, 8, 10))
    d = client.get("/auswertungen/einnahmen?jahr=2026&vergleich=2025").json()
    m = {x["monat"]: x for x in d["aktuell"]["monate"]}
    assert m[8]["einnahmen"] == "100.00" and m[8]["vorlaeufig"] == "100.00" and m[8]["saetze"][0]["satz"] == "3.8"
    assert m[10]["einnahmen"] == "50.00" and m[10]["taxen"] == "9.85" and m[10]["umsatz_mwst_pflichtig"] == "40.15"
    rest = m[HEUTE.month] if HEUTE.year == 2026 else None
    if rest is not None and HEUTE.month != 10:
        assert rest["einnahmen"] == "41.40" and rest["zahlungsarten"] == {"TWINT": "41.40"}
    t = d["aktuell"]["total"]
    assert (t["einnahmen"], t["taxen"], t["umsatz_mwst_pflichtig"]) == ("191.40", "18.00", "173.40")
    assert t["mwst"] == str((Decimal("173.40") - Decimal("173.40") / Decimal("1.038")).quantize(Decimal("0.01")))
    assert d["vergleich"]["total"]["einnahmen"] == "0.00"


def test_uebernachtungen_und_taxen_je_nacht(client, db, grunddaten):  # noqa: F811
    bid = _aufenthalt(db, e=2, k=1)
    client.post(f"/aufenthalte/{bid}/leistungen", json={"art": "erwachsene", "von": "2026-07-01", "bis": "2026-07-02",
                                                         "kurtaxepflichtig": False})
    d = client.get("/auswertungen/uebernachtungen?jahr=2026").json()["aktuell"]
    m = {x["monat"]: x for x in d["monate"]}
    assert (m[6]["ankuenfte"], m[6]["erwachsene"], m[6]["kinder"], m[6]["kurtaxe"], m[6]["beherbergungsabgabe"]) == (1, 2, 1, "7.00", "2.00")
    assert (m[7]["erwachsene"], m[7]["erwachsene_kurtaxe"], m[7]["kurtaxe"], m[7]["beherbergungsabgabe"]) == (3, 2, "7.00", "3.00")
    assert m[7]["plaetze"] == {"camper": 1}
    assert (d["total"]["personennaechte"], d["total"]["taxen"]) == (7, "19.00")


def test_saison_mit_excel_und_pdf(client, db, grunddaten):  # noqa: F811
    bid = _aufenthalt(db, anzahlung="50")
    client.post(f"/rechnungen/aus-aufenthalt/{bid}", json={})          # bleibt offen
    _anzahlung_ohne_aufenthalt(db, "100", date(2026, 8, 10))
    s = client.get(f"/auswertungen/saison?jahr={HEUTE.year}").json()
    assert s["rechnungen"]["anzahl"] == 1 and s["rechnungen"]["total"] == "91.40"
    assert s["mwst_auf_rechnungen"][0]["satz"] == "3.8" and s["mwst_auf_rechnungen"][0]["brutto"] == "73.40"
    assert s["taxen_total"] == "18.00" and s["offene_rechnungen"][0]["restbetrag"] == "41.40"
    assert s["leistungen"][0]["bezeichnung"] == "Camper" and s["leistungen"][0]["betrag"] == "34.00"
    assert all("E" not in l["menge"] for l in s["leistungen"])
    x = client.get(f"/auswertungen/saison/{HEUTE.year}.xlsx")
    assert x.status_code == 200
    wb = load_workbook(BytesIO(x.content))
    assert wb.sheetnames == ["Übersicht", "Einnahmen & MWST", "Übernachtungen & Taxen", "Leistungen", "Offen"]
    assert wb["Offen"].max_row >= 2
    p = client.get(f"/auswertungen/saison/{HEUTE.year}.pdf")
    assert p.status_code == 200 and p.content.startswith(b"%PDF")
    assert HEUTE.year in client.get("/auswertungen/jahre").json()
