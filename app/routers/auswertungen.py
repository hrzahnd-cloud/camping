"""
Auswertungen (Konzeptdokument Abschnitt 13).

Liefert aktuell die Rohdaten als JSON. Die Darstellung im Programm
(Tabelle/Diagramm) sowie der PDF-/Excel-Export sind Aufgabe des
Frontends bzw. eines noch zu ergänzenden Export-Endpunkts
(z.B. mit `openpyxl` für Excel) – hier bewusst zunächst nur die
Datengrundlage, um die Berechnungslogik zentral und testbar zu halten.
"""
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.artikel import Artikel
from app.models.buchung import Gast
from app.models.rechnung import Rechnung, Rechnungsposition
from app.models.reservation import Zahlung

router = APIRouter(prefix="/auswertungen", tags=["Auswertungen"])


@router.get("/umsatz-nach-kunde")
def umsatz_nach_kunde(
    von: date, bis: date, nur_bezahlt: bool = True, db: Session = Depends(get_db)
):
    stmt = (
        select(
            Gast.id, Gast.vorname, Gast.nachname, func.sum(Rechnung.gesamtbetrag).label("umsatz")
        )
        .join(Rechnung, Rechnung.kunde_id == Gast.id)
        .where(Rechnung.datum >= von, Rechnung.datum <= bis)
        .group_by(Gast.id, Gast.vorname, Gast.nachname)
        .order_by(func.sum(Rechnung.gesamtbetrag).desc())
    )
    if nur_bezahlt:
        stmt = stmt.where(Rechnung.status == "bezahlt")

    zeilen = db.execute(stmt).all()
    return [
        {"kunde_id": str(r.id), "name": f"{r.vorname} {r.nachname}", "umsatz": float(r.umsatz)}
        for r in zeilen
    ]


@router.get("/umsatz-pro-monat")
def umsatz_pro_monat(von: date, bis: date, nur_bezahlt: bool = True, db: Session = Depends(get_db)):
    monat_ausdruck = func.to_char(Rechnung.datum, "YYYY-MM")
    stmt = (
        select(monat_ausdruck.label("monat"), func.sum(Rechnung.gesamtbetrag).label("umsatz"))
        .where(Rechnung.datum >= von, Rechnung.datum <= bis)
        .group_by(monat_ausdruck)
        .order_by(monat_ausdruck)
    )
    if nur_bezahlt:
        stmt = stmt.where(Rechnung.status == "bezahlt")

    zeilen = db.execute(stmt).all()
    return [{"monat": r.monat, "umsatz": float(r.umsatz)} for r in zeilen]


@router.get("/nach-artikel")
def umsatz_nach_artikel(von: date, bis: date, db: Session = Depends(get_db)):
    stmt = (
        select(
            Artikel.id,
            Artikel.bezeichnung,
            func.sum(Rechnungsposition.menge).label("menge"),
            func.sum(Rechnungsposition.betrag).label("umsatz"),
        )
        .join(Rechnungsposition, Rechnungsposition.artikel_id == Artikel.id)
        .join(Rechnung, Rechnung.id == Rechnungsposition.rechnung_id)
        .where(Rechnung.datum >= von, Rechnung.datum <= bis)
        .group_by(Artikel.id, Artikel.bezeichnung)
        .order_by(func.sum(Rechnungsposition.betrag).desc())
    )
    zeilen = db.execute(stmt).all()
    return [
        {
            "artikel_id": str(r.id), "bezeichnung": r.bezeichnung,
            "menge": float(r.menge), "umsatz": float(r.umsatz),
        }
        for r in zeilen
    ]


@router.get("/zahlungsmethoden")
def zahlungsmethoden_ueber_zeitraum(
    von: date, bis: date, db: Session = Depends(get_db)
):
    """Gruppiert eingegangene Zahlungen nach Zahlungsart im gewählten Zeitraum."""
    stmt = (
        select(Zahlung.zahlungsart, func.sum(Zahlung.betrag).label("summe"), func.count().label("anzahl"))
        .where(
            Zahlung.status == "eingegangen",
            Zahlung.eingegangen_am >= von,
            Zahlung.eingegangen_am <= bis,
        )
        .group_by(Zahlung.zahlungsart)
        .order_by(func.sum(Zahlung.betrag).desc())
    )
    zeilen = db.execute(stmt).all()
    return [
        {"zahlungsart": r.zahlungsart, "summe": float(r.summe), "anzahl": r.anzahl}
        for r in zeilen
    ]
