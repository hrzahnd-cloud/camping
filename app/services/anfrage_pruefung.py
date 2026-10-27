"""Vollständigkeitsprüfung von Reservationsanfragen (Konzept Abschnitt 10.1)."""
from app.models.reservation import Reservationsanfrage


def pruefe_vollstaendigkeit(anfrage: Reservationsanfrage) -> tuple[bool, list[str]]:
    """Gibt (vollstaendig, liste_fehlender_felder) zurück."""
    fehlend = []
    if not anfrage.gast_email:
        fehlend.append("gast_email")
    if not anfrage.gewuenscht_von or not anfrage.gewuenscht_bis:
        fehlend.append("zeitraum")
    elif anfrage.gewuenscht_bis <= anfrage.gewuenscht_von:
        fehlend.append("zeitraum_ungueltig")
    if not anfrage.stellplatz_typ:
        fehlend.append("stellplatz_typ")
    if (anfrage.anzahl_erwachsene or 0) < 1:
        fehlend.append("anzahl_erwachsene")
    return (len(fehlend) == 0, fehlend)


PRUEF_STATUS = {"neu", "unvollstaendig", "geprueft_vollstaendig"}
"""Status, die allein aus der Vollständigkeitsprüfung folgen. Spätere
Workflow-Status (Antwort gesendet, akzeptiert, ...) setzt eine Person."""


def wende_pruefung_an(anfrage: Reservationsanfrage) -> None:
    """Setzt vollstaendig, fehlende_angaben und – solange die Anfrage noch nicht
    weiterbearbeitet wurde – den Status gemäss Prüfergebnis."""
    vollstaendig, fehlend = pruefe_vollstaendigkeit(anfrage)
    anfrage.vollstaendig = vollstaendig
    anfrage.fehlende_angaben = ",".join(fehlend) if fehlend else None
    if anfrage.status is None or anfrage.status in PRUEF_STATUS:
        anfrage.status = "geprueft_vollstaendig" if vollstaendig else "unvollstaendig"
