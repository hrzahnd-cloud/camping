"""Saison-Zusammenstellung als Excel (für die Buchhaltung) und als PDF (zum Ausdrucken)."""
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

CHF = '#,##0.00'
KOPF = PatternFill("solid", fgColor="E1EEF4")
FETT = Font(bold=True)


def _f(x) -> float:
    return float(x) if x not in (None, "") else 0.0


def _blatt(wb, titel, kopf, zeilen, geld_spalten=(), total=None, breiten=None):
    ws = wb.create_sheet(titel)
    ws.append(kopf)
    for c in ws[1]:
        c.font, c.fill = FETT, KOPF
        c.alignment = Alignment(vertical="center", wrap_text=True)
    for z in zeilen:
        ws.append(z)
    if total:
        ws.append(total)
        for c in ws[ws.max_row]:
            c.font = FETT
    for i in geld_spalten:
        for zeile in ws.iter_rows(min_row=2, min_col=i, max_col=i):
            zeile[0].number_format = CHF
    for i, b in enumerate(breiten or [], start=1):
        ws.column_dimensions[get_column_letter(i)].width = b
    ws.freeze_panes = "A2"
    return ws


def excel(saison: dict, einnahmen: dict, uebernachtungen: dict, betrieb: str = "") -> bytes:
    j = saison["jahr"]
    wb = Workbook()
    ws = wb.active
    ws.title = "Übersicht"
    r = saison["rechnungen"]
    zeilen = [
        [f"Saison-Zusammenstellung {j}" + (f" – {betrieb}" if betrieb else "")], [],
        ["Rechnungen", r["anzahl"], f"Nr. {r['von']} – {r['bis']}" if r["von"] else ""],
        ["davon storniert (nicht gezählt)", r["storniert"]],
        ["Total Rechnungen (inkl. MWST und Taxen)", _f(r["total"])],
        ["darin verrechnete Anzahlungen", _f(r["anzahlungen"])], [],
        ["MWST auf den Rechnungstotalen", "Brutto", "MWST", "Netto"],
        *[[f"{m['satz']} %", _f(m["brutto"]), _f(m["mwst"]), _f(m["netto"])] for m in saison["mwst_auf_rechnungen"]], [],
        ["Taxen (durchlaufend, ohne MWST)", "Betrag"],
        *[[t["bezeichnung"], _f(t["betrag"])] for t in saison["taxen"]],
        ["Total Taxen", _f(saison["taxen_total"])], [],
        ["Einnahmen nach Zahlungseingang (vereinnahmt)", "Betrag"],
        *[[k, _f(v)] for k, v in saison["einnahmen"]["zahlungsarten"].items()],
        ["Total Einnahmen", _f(saison["einnahmen"]["einnahmen"])],
        ["davon Taxen", _f(saison["einnahmen"]["taxen"])],
        ["davon MWST-pflichtiger Umsatz", _f(saison["einnahmen"]["umsatz_mwst_pflichtig"])],
        ["darin MWST", _f(saison["einnahmen"]["mwst"])],
        ["davon Anzahlungen ohne Rechnung (vorläufig Beherbergung)", _f(saison["einnahmen"]["vorlaeufig"])],
    ]
    for z in zeilen:
        ws.append(z)
    ws["A1"].font = Font(bold=True, size=14)
    for zeile in ws.iter_rows(min_row=3):
        for c in zeile[1:]:
            if isinstance(c.value, float):
                c.number_format = CHF
        if zeile[0].value and (str(zeile[0].value).startswith(("MWST auf", "Taxen (", "Einnahmen nach", "Total"))):
            zeile[0].font = FETT
    ws.column_dimensions["A"].width = 58
    for col in "BCD":
        ws.column_dimensions[col].width = 16

    saetze = sorted({s["satz"] for m in einnahmen["monate"] for s in m["saetze"]})
    arten = sorted({k for m in einnahmen["monate"] for k in m["zahlungsarten"]})
    _blatt(wb, "Einnahmen & MWST",
           ["Monat", "Einnahmen", "Taxen", "MWST-pflichtig", *[f"MWST {s} %" for s in saetze], *arten, "vorläufig (ohne Rechnung)"],
           [[m["name"], _f(m["einnahmen"]), _f(m["taxen"]), _f(m["umsatz_mwst_pflichtig"]),
             *[_f(next((x["mwst"] for x in m["saetze"] if x["satz"] == s), 0)) for s in saetze],
             *[_f(m["zahlungsarten"].get(a, 0)) for a in arten], _f(m["vorlaeufig"])] for m in einnahmen["monate"]],
           geld_spalten=range(2, 6 + len(saetze) + len(arten)),
           total=["Total", _f(einnahmen["total"]["einnahmen"]), _f(einnahmen["total"]["taxen"]),
                  _f(einnahmen["total"]["umsatz_mwst_pflichtig"]),
                  *[_f(next((x["mwst"] for x in einnahmen["total"]["saetze"] if x["satz"] == s), 0)) for s in saetze],
                  *[_f(einnahmen["total"]["zahlungsarten"].get(a, 0)) for a in arten], _f(einnahmen["total"]["vorlaeufig"])],
           breiten=[14] + [15] * (5 + len(saetze) + len(arten)))

    plaetze = sorted({k for m in uebernachtungen["monate"] for k in m["plaetze"]})
    u = uebernachtungen
    _blatt(wb, "Übernachtungen & Taxen",
           ["Monat", "Ankünfte", "Personennächte", "Erwachsene", "davon kurtaxepflichtig", "Kinder", "Kleinkinder",
            "Kurtaxe", "Beherbergungsabgabe", "Taxen total", *[f"Nächte {p}" for p in plaetze]],
           [[m["name"], m["ankuenfte"], m["personennaechte"], m["erwachsene"], m["erwachsene_kurtaxe"], m["kinder"], m["kleinkinder"],
             _f(m["kurtaxe"]), _f(m["beherbergungsabgabe"]), _f(m["taxen"]), *[m["plaetze"].get(p, 0) for p in plaetze]]
            for m in u["monate"]],
           geld_spalten=(8, 9, 10),
           total=["Total", u["total"]["ankuenfte"], u["total"]["personennaechte"], u["total"]["erwachsene"], u["total"]["erwachsene_kurtaxe"],
                  u["total"]["kinder"], u["total"]["kleinkinder"], _f(u["total"]["kurtaxe"]), _f(u["total"]["beherbergungsabgabe"]),
                  _f(u["total"]["taxen"]), *[u["total"]["plaetze"].get(p, 0) for p in plaetze]],
           breiten=[14, 10, 15, 12, 14, 10, 12, 12, 15, 12] + [12] * len(plaetze))

    _blatt(wb, "Leistungen", ["Leistung", "Menge", "MWST %", "Betrag inkl. MWST"],
           [[l["bezeichnung"], float(l["menge"]), float(l["satz"]), _f(l["betrag"])] for l in saison["leistungen"]],
           geld_spalten=(4,), breiten=[36, 12, 10, 18])
    _blatt(wb, "Offen", ["Art", "Datum", "Gast", "Nummer", "Betrag"],
           [["Rechnung offen", str(o["datum"]), o["gast"], o["nummer"], _f(o["restbetrag"])] for o in saison["offene_rechnungen"]]
           + [["Anzahlung ohne Rechnung", str(a["datum"]), a["gast"], a["reservation"] or "", _f(a["betrag"])]
              for a in saison["anzahlungen_ohne_rechnung"]],
           geld_spalten=(5,), breiten=[24, 12, 28, 14, 14])
    puffer = BytesIO()
    wb.save(puffer)
    return puffer.getvalue()


def pdf(saison: dict, einnahmen: dict, uebernachtungen: dict, betrieb: str = "") -> bytes:
    puffer = BytesIO()
    c = canvas.Canvas(puffer, pagesize=A4)
    c.setTitle(f"Saison {saison['jahr']}")
    breite, hoehe = A4
    rand, rechts = 45, breite - 45
    tief, leise = HexColor("#143040"), HexColor("#56646b")
    y = hoehe - 55

    def neue_seite():
        nonlocal y
        c.showPage()
        y = hoehe - 55

    def titel(text):
        nonlocal y
        if y < 140:
            neue_seite()
        y -= 10
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(tief)
        c.drawString(rand, y, text)
        y -= 16

    def zeile(texte, spalten, fett=False):
        nonlocal y
        if y < 60:
            neue_seite()
        c.setFont("Helvetica-Bold" if fett else "Helvetica", 8.5)
        c.setFillColor(HexColor("#1b2428"))
        for i, (t, x) in enumerate(zip(texte, spalten)):
            (c.drawString if i == 0 else c.drawRightString)(x, y, str(t))
        y -= 12

    c.setFont("Helvetica-Bold", 16)
    c.setFillColor(tief)
    c.drawString(rand, y, f"Saison-Zusammenstellung {saison['jahr']}")
    y -= 15
    c.setFont("Helvetica", 9)
    c.setFillColor(leise)
    c.drawString(rand, y, (betrieb + " · " if betrieb else "") + "Beträge in CHF; MWST nach vereinnahmtem Entgelt und auf den Rechnungstotalen")
    y -= 10

    r = saison["rechnungen"]
    titel("Rechnungen")
    zeile(["Anzahl Rechnungen" + (f" (Nr. {r['von']} – {r['bis']})" if r["von"] else ""), r["anzahl"]], [rand, rechts])
    zeile(["davon storniert (nicht gezählt)", r["storniert"]], [rand, rechts])
    zeile(["Total Rechnungen inkl. MWST und Taxen", r["total"]], [rand, rechts], True)
    zeile(["darin verrechnete Anzahlungen", r["anzahlungen"]], [rand, rechts])

    titel("MWST auf den Rechnungstotalen")
    sp = [rand, rand + 300, rand + 390, rechts]
    zeile(["Satz", "Brutto", "MWST", "Netto"], sp, True)
    for m in saison["mwst_auf_rechnungen"]:
        zeile([f"{m['satz']} %", m["brutto"], m["mwst"], m["netto"]], sp)

    titel("Taxen (durchlaufend, ohne MWST)")
    for t in saison["taxen"]:
        zeile([t["bezeichnung"], t["betrag"]], [rand, rechts])
    zeile(["Total Taxen", saison["taxen_total"]], [rand, rechts], True)

    titel("Einnahmen und MWST pro Monat (nach Zahlungseingang)")
    sp = [rand, rand + 150, rand + 235, rand + 330, rand + 415, rechts]
    zeile(["Monat", "Einnahmen", "Taxen", "MWST-pflichtig", "MWST", "vorläufig"], sp, True)
    for m in einnahmen["monate"]:
        if m["einnahmen"] != "0.00":
            zeile([m["name"], m["einnahmen"], m["taxen"], m["umsatz_mwst_pflichtig"], m["mwst"], m["vorlaeufig"]], sp)
    t = einnahmen["total"]
    zeile(["Total", t["einnahmen"], t["taxen"], t["umsatz_mwst_pflichtig"], t["mwst"], t["vorlaeufig"]], sp, True)
    for k, v in t["zahlungsarten"].items():
        zeile([f"  davon {k}", v], [rand, sp[1]])
    c.setFont("Helvetica", 7.5)
    c.setFillColor(leise)
    c.drawString(rand, y - 2, "«vorläufig»: Anzahlungen ohne Rechnung (noch nicht abgereist oder nicht erschienen), ganz als Beherbergung gerechnet.")
    y -= 14

    titel("Übernachtungen und Taxen pro Monat (nach Nacht, Kontrolle zu Feratel)")
    sp = [rand, rand + 120, rand + 190, rand + 260, rand + 330, rand + 410, rechts]
    zeile(["Monat", "Personennächte", "Erwachsene", "Kinder", "Kleinkinder", "Kurtaxe", "Beherb.-Abgabe"], sp, True)
    for m in uebernachtungen["monate"]:
        if m["personennaechte"]:
            zeile([m["name"], m["personennaechte"], m["erwachsene"], m["kinder"], m["kleinkinder"], m["kurtaxe"], m["beherbergungsabgabe"]], sp)
    u = uebernachtungen["total"]
    zeile(["Total", u["personennaechte"], u["erwachsene"], u["kinder"], u["kleinkinder"], u["kurtaxe"], u["beherbergungsabgabe"]], sp, True)

    if saison["leistungen"]:
        titel("Umsatz je Leistung (Rechnungen, inkl. MWST)")
        for l in saison["leistungen"]:
            zeile([l["bezeichnung"], l["menge"], f"{l['satz']} %", l["betrag"]], [rand, rand + 330, rand + 410, rechts])

    if saison["offene_rechnungen"] or saison["anzahlungen_ohne_rechnung"]:
        titel("Offen bzw. noch nicht abgerechnet")
        for o in saison["offene_rechnungen"]:
            zeile([f"Rechnung {o['nummer']} · {o['gast']}", o["restbetrag"]], [rand, rechts])
        for a in saison["anzahlungen_ohne_rechnung"]:
            zeile([f"Anzahlung {a['datum'].strftime('%d.%m.%Y')} · {a['gast']} ({a['reservation'] or '–'})", a["betrag"]], [rand, rechts])
    c.showPage()
    c.save()
    return puffer.getvalue()
