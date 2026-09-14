"""
Feratel Deskline 3.0 VT PMS Web Services – Anbindung.

STATUS: NICHT IMPLEMENTIERT (bewusster Platzhalter).

Grund: Für die tatsächliche SOAP/XML-Kommunikation fehlt die technische
Dokumentation (WSDL) von Feratel. Diese wird erst nach Freischaltung als
PMS-Partner durch Thun-Thunersee Tourismus bereitgestellt (siehe
Konzeptdokument Abschnitt 5 und offene Punkte).

Sobald die WSDL vorliegt, ist hier zu ergänzen:
  1. XML-Meldeblatt aus Aufenthalt + Gast erzeugen (siehe `_baue_meldeblatt_stub`
     als Ausgangspunkt für die tatsächliche Feldstruktur)
  2. HTTP POST/SOAP-Request an `FeratelKonfiguration.endpoint_url` senden
     (empfohlen: Bibliothek `zeep` für SOAP-Clients)
  3. Antwort auswerten, FeratelMeldung.status/fehlercode/antwort_roh setzen

Bis dahin liefert `sende_meldung()` einen klaren Fehler, statt so zu tun,
als würde eine echte Übertragung stattfinden.
"""
from app.models.buchung import Aufenthalt
from app.models.meldungen import FeratelKonfiguration, FeratelMeldung


class FeratelNichtKonfiguriert(Exception):
    """Wird ausgelöst, solange keine gültige FeratelKonfiguration aktiv ist."""


def _baue_meldeblatt_stub(aufenthalt: Aufenthalt) -> dict:
    """
    Platzhalter für die künftige XML-Struktur. Enthält bereits die aus
    heutiger Sicht wahrscheinlich benötigten Felder (siehe Konzept 5),
    muss aber nach Erhalt der WSDL überarbeitet werden.
    """
    gast = aufenthalt.gast
    return {
        "ankunft": aufenthalt.ankunft.isoformat(),
        "abreise": aufenthalt.abreise.isoformat(),
        "gast_vorname": gast.vorname,
        "gast_nachname": gast.nachname,
        "gast_plz": gast.plz,
        "gast_land": gast.land,
    }


def sende_meldung(aufenthalt: Aufenthalt, konfiguration: FeratelKonfiguration) -> FeratelMeldung:
    """
    Würde einen Aufenthalt an Feratel melden. Aktuell nicht funktionsfähig.

    Raises:
        FeratelNichtKonfiguriert: immer, bis die echte SOAP-Anbindung
            implementiert und `konfiguration.aktiv` gesetzt ist.
    """
    if not konfiguration.aktiv:
        raise FeratelNichtKonfiguriert(
            "Feratel-Schnittstelle ist noch nicht aktiv konfiguriert. "
            "Voraussetzung: PMS-Partner-Freischaltung durch Thun-Thunersee "
            "Tourismus und Erhalt der WSDL-Dokumentation (siehe Konzeptdokument)."
        )
    raise NotImplementedError(
        "Die tatsächliche SOAP/XML-Kommunikation mit Feratel Deskline 3.0 "
        "ist noch zu implementieren, sobald die WSDL vorliegt."
    )
