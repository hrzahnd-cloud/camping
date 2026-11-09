"""
Antwortmails auf Reservationsanfragen (Konzept Abschnitt 10.2/10.3).

- Betriebsangaben (Signatur, Infoblock, IBAN, BIC, Kontoinhaber, TWINT) liegen
  als Einstellungen in der Datenbank und werden in der Oberfläche gepflegt.
- Vorlagen je Sprache (DE/FR/IT/EN) liegen in `email_vorlage` und sind in der
  Oberfläche bearbeitbar. Fehlende Startvorlagen werden beim Start ergänzt,
  bestehende (auch geänderte) bleiben unverändert.
- Eine Person bereitet die Antwort vor (Anzahlung von Hand, Frist optional),
  kann den Text anpassen und verschickt ihn – bis das Mailkonto angebunden
  ist – aus dem eigenen Mailprogramm. Danach wird der Versand protokolliert.
"""
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.einstellungen import AppEinstellung
from app.models.kommunikation import EmailVorlage
from app.models.reservation import Reservationsanfrage

TYP_ERSTANTWORT = "erstantwort_zahlungsinfo"
TYP_FREI = "freie_antwort"
TYP_BESTAETIGUNG = "bestaetigung_definitiv"
VORLAGENTYPEN = {
    TYP_ERSTANTWORT: "Antwort mit Anzahlung",
    TYP_FREI: "Freie Antwort",
    TYP_BESTAETIGUNG: "Bestätigung definitiv",
}
"""Freie Antwort: nur Anrede, eigener Text und Signatur – für Rückfragen
(«Sind Hunde erlaubt?») und das Hin und Her vor der eigentlichen Reservation."""
SPRACHEN = ("de", "fr", "it", "en")

# --- Betriebsangaben ------------------------------------------------------------

@dataclass(frozen=True)
class Feld:
    schluessel: str
    bezeichnung: str
    hinweis: str
    mehrzeilig: bool = False


BETRIEBSFELDER: tuple[Feld, ...] = (
    Feld("signatur", "Signatur", "Steht in jeder Antwort direkt unter dem Gruss (Name, Adresse, Telefon, Web).", True),
    Feld("infoblock", "Infoblock", "Wird unverändert unter die Signatur gesetzt, z.B. Check-in-Zeiten, Hunde, Links zu Hausregeln und AGB.", True),
    Feld("iban", "IBAN", "Konto für die Anzahlung."),
    Feld("bic", "BIC", ""),
    Feld("kontoinhaber", "Kontoinhaber", "Optional, erscheint unter IBAN/BIC."),
    Feld("twint", "TWINT-Nummer", "Leer lassen, solange TWINT nicht angeboten wird. Sobald ausgefüllt, erscheint TWINT in der Antwort."),
    Feld("rechnung_absender", "Absender auf der Rechnung", "Name und Adresse des Betriebs, oben links auf jeder Rechnung.", True),
    Feld("mwst_nummer", "MWST-Nummer", "Erscheint auf der Rechnung, z.B. CHE-123.456.789 MWST."),
)
BETRIEBSSCHLUESSEL = {f.schluessel for f in BETRIEBSFELDER}


def betriebsangaben(db: Session) -> dict[str, str]:
    gespeichert = {
        e.schluessel: e.wert
        for e in db.execute(select(AppEinstellung).where(AppEinstellung.schluessel.in_(BETRIEBSSCHLUESSEL))).scalars()
    }
    return {f.schluessel: gespeichert.get(f.schluessel, "") for f in BETRIEBSFELDER}


def betriebsangaben_setzen(db: Session, werte: dict[str, str]) -> dict[str, str]:
    for schluessel, wert in werte.items():
        if schluessel not in BETRIEBSSCHLUESSEL:
            continue
        wert = (wert or "").strip("\n").rstrip()
        eintrag = db.get(AppEinstellung, schluessel)
        if eintrag is None:
            db.add(AppEinstellung(schluessel=schluessel, wert=wert))
        else:
            eintrag.wert = wert
    db.commit()
    return betriebsangaben(db)


# --- Startvorlagen ----------------------------------------------------------------

STARTVORLAGEN = {
    "de": (
        "Ihre Reservation vom {{anreise}} bis {{abreise}} – Panorama-Camping Aeschi",
        """Guten Tag {{gastName}}

Vielen Dank für Ihre Anfrage. Gerne reservieren wir für Sie:

Anreise: {{anreise}}
Abreise: {{abreise}} ({{naechte}} Nächte)
Stellplatz: {{stellplatzTyp}}
Personen: {{personen}}

{{zahlungsinfo}}

Sobald die Anzahlung bei uns eingegangen ist, ist Ihre Reservation definitiv.

Wir freuen uns auf Ihren Besuch.

Freundliche Grüsse
{{signatur}}

{{infoblock}}""",
    ),
    "fr": (
        "Votre réservation du {{anreise}} au {{abreise}} – Panorama-Camping Aeschi",
        """Bonjour {{gastName}},

Merci beaucoup pour votre demande. Nous avons le plaisir de réserver pour vous :

Arrivée : {{anreise}}
Départ : {{abreise}} ({{naechte}} nuits)
Emplacement : {{stellplatzTyp}}
Personnes : {{personen}}

{{zahlungsinfo}}

Votre réservation sera définitive dès réception de l'acompte.

Nous nous réjouissons de votre visite.

Meilleures salutations
{{signatur}}

{{infoblock}}""",
    ),
    "it": (
        "La sua prenotazione dal {{anreise}} al {{abreise}} – Panorama-Camping Aeschi",
        """Buongiorno {{gastName}},

grazie mille per la sua richiesta. Siamo lieti di riservare per lei:

Arrivo: {{anreise}}
Partenza: {{abreise}} ({{naechte}} notti)
Piazzola: {{stellplatzTyp}}
Persone: {{personen}}

{{zahlungsinfo}}

La prenotazione sarà definitiva non appena avremo ricevuto l'acconto.

Ci rallegriamo della sua visita.

Cordiali saluti
{{signatur}}

{{infoblock}}""",
    ),
    "en": (
        "Your reservation from {{anreise}} to {{abreise}} – Panorama-Camping Aeschi",
        """Dear {{gastName}},

Thank you very much for your enquiry. We are pleased to reserve the following for you:

Arrival: {{anreise}}
Departure: {{abreise}} ({{naechte}} nights)
Pitch: {{stellplatzTyp}}
Guests: {{personen}}

{{zahlungsinfo}}

Your reservation will be confirmed as soon as we have received the deposit.

We look forward to welcoming you.

Kind regards
{{signatur}}

{{infoblock}}""",
    ),
}


STARTVORLAGEN_FREI = {
    "de": ("{{antwortBetreff}}", "Guten Tag {{gastName}}\n\nFreundliche Grüsse\n{{signatur}}"),
    "fr": ("{{antwortBetreff}}", "Bonjour {{gastName}},\n\nMeilleures salutations\n{{signatur}}"),
    "it": ("{{antwortBetreff}}", "Buongiorno {{gastName}},\n\nCordiali saluti\n{{signatur}}"),
    "en": ("{{antwortBetreff}}", "Dear {{gastName}},\n\nKind regards\n{{signatur}}"),
}
STARTVORLAGEN_BESTAETIGUNG = {
    "de": (
        "Bestätigung Ihrer Reservation vom {{anreise}} bis {{abreise}} – Panorama-Camping Aeschi",
        """Guten Tag {{gastName}}

{{zahlungsbestaetigung}}

Ihre Reservation ist definitiv gebucht:

Anreise: {{anreise}}
Abreise: {{abreise}} ({{naechte}} Nächte)
Stellplatz: {{stellplatzTyp}}
Personen: {{personen}}

{{preisProNacht}}

Wir freuen uns auf Ihren Besuch.

Freundliche Grüsse
{{signatur}}""",
    ),
    "fr": (
        "Confirmation de votre réservation du {{anreise}} au {{abreise}} – Panorama-Camping Aeschi",
        """Bonjour {{gastName}},

{{zahlungsbestaetigung}}

Votre réservation est définitive :

Arrivée : {{anreise}}
Départ : {{abreise}} ({{naechte}} nuits)
Emplacement : {{stellplatzTyp}}
Personnes : {{personen}}

{{preisProNacht}}

Nous nous réjouissons de votre visite.

Meilleures salutations
{{signatur}}""",
    ),
    "it": (
        "Conferma della sua prenotazione dal {{anreise}} al {{abreise}} – Panorama-Camping Aeschi",
        """Buongiorno {{gastName}},

{{zahlungsbestaetigung}}

La sua prenotazione è definitiva:

Arrivo: {{anreise}}
Partenza: {{abreise}} ({{naechte}} notti)
Piazzola: {{stellplatzTyp}}
Persone: {{personen}}

{{preisProNacht}}

Ci rallegriamo della sua visita.

Cordiali saluti
{{signatur}}""",
    ),
    "en": (
        "Confirmation of your reservation from {{anreise}} to {{abreise}} – Panorama-Camping Aeschi",
        """Dear {{gastName}},

{{zahlungsbestaetigung}}

Your reservation is now confirmed:

Arrival: {{anreise}}
Departure: {{abreise}} ({{naechte}} nights)
Pitch: {{stellplatzTyp}}
Guests: {{personen}}

{{preisProNacht}}

We look forward to welcoming you.

Kind regards
{{signatur}}""",
    ),
}
_STARTVORLAGEN_JE_TYP = {TYP_ERSTANTWORT: STARTVORLAGEN, TYP_FREI: STARTVORLAGEN_FREI,
                         TYP_BESTAETIGUNG: STARTVORLAGEN_BESTAETIGUNG}


def startvorlagen_ergaenzen(db: Session) -> int:
    """
    Legt fehlende Vorlagen an (idempotent). Gibt die Anzahl neuer Vorlagen zurück.
    Unveränderte Bestätigungs-Vorlagen der früheren Fassung erhalten den
    Platzhalter {{preisProNacht}}; angepasste Vorlagen bleiben, wie sie sind.
    """
    vorlagen = list(db.execute(select(EmailVorlage)).scalars())
    vorhanden = {(v.typ, v.sprache) for v in vorlagen}
    neu = 0
    for v in vorlagen:
        start = STARTVORLAGEN_BESTAETIGUNG.get(v.sprache)
        if v.typ == TYP_BESTAETIGUNG and start and v.koerper == start[1].replace("\n\n{{preisProNacht}}", ""):
            v.koerper = start[1]
            neu += 1
    for typ, vorlagen in _STARTVORLAGEN_JE_TYP.items():
        for sprache, (betreff, koerper) in vorlagen.items():
            if (typ, sprache) not in vorhanden:
                db.add(EmailVorlage(typ=typ, sprache=sprache, betreff=betreff, koerper=koerper, aktiv=True))
                neu += 1
    if neu:
        db.commit()
    return neu


# --- Platzhalter ------------------------------------------------------------------

PLATZHALTER = {
    "gastName": "Name des Gastes aus der Anfrage",
    "anreise": "Anreisedatum, in der Sprache der Mail",
    "abreise": "Abreisedatum, in der Sprache der Mail",
    "naechte": "Anzahl Nächte",
    "stellplatzTyp": "Stellplatz-Typ, übersetzt (z.B. Wohnwagen / caravan)",
    "personen": "Personen mit richtiger Einzahl/Mehrzahl, z.B. «2 Erwachsene, 1 Kind»",
    "erwachsene": "Anzahl Erwachsene (nur die Zahl)",
    "kinder": "Anzahl Kinder inkl. Kleinkinder (nur die Zahl)",
    "betrag": "Anzahlung, beim Vorbereiten von Hand eingegeben (z.B. CHF 120.00)",
    "zahlungsfrist": "Zahlungsfrist, falls beim Vorbereiten angegeben (sonst leer)",
    "zahlungsinfo": "Ganzer Absatz zur Anzahlung: Betrag, IBAN/BIC, Frist und TWINT, soweit vorhanden",
    "antwortBetreff": "Betreff einer Antwort: «Re: …» auf die letzte Mail des Gastes, sonst «Ihre Anfrage – Panorama-Camping Aeschi»",
    "anfrageNummer": "Nummer der Anfrage, z.B. 2026-042 (steht automatisch auch im Betreff)",
    "anzahlungErhalten": "Gutgeschriebene Anzahlung beim Akzeptieren, z.B. CHF 85.40 (sonst leer)",
    "zahlungsbestaetigung": "Satz «Vielen Dank für Ihre Anzahlung von …», leer wenn ohne Anzahlung akzeptiert",
    "preisProNacht": "Unverbindlicher Preis pro Nacht mit Aufstellung (Personen, Stellplatz, Umweltabgabe, Taxen; je Saison) – nur mit Modul «Artikel & Preise»",
    "signatur": "Signatur aus den Betriebsangaben",
    "infoblock": "Infoblock aus den Betriebsangaben",
}

_PLATZHALTER_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")

_MONATE = {
    "de": ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"],
    "fr": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"],
    "it": ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"],
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
}

_TYPEN = {
    "zeltwiese": {"de": "Zelt", "fr": "tente", "it": "tenda", "en": "tent"},
    "wohnwagen": {"de": "Wohnwagen", "fr": "caravane", "it": "roulotte", "en": "caravan"},
    "camper": {"de": "Camper / Wohnmobil", "fr": "camping-car", "it": "camper", "en": "camper van / motorhome"},
    "zwaergli": {"de": "Zwärgli", "fr": "Zwärgli (cabane)", "it": "Zwärgli (casetta)", "en": "Zwärgli (cabin)"},
    "spycher": {"de": "Spycher", "fr": "Spycher (cabane)", "it": "Spycher (casetta)", "en": "Spycher (cabin)"},
}

_ZAHLUNG = {
    "de": ("Für die Reservation bitten wir Sie um eine Anzahlung von {betrag} auf folgendes Konto:",
           "Bitte überweisen Sie den Betrag bis {frist}.",
           "Die Anzahlung kann auch per TWINT an {twint} bezahlt werden."),
    "fr": ("Pour confirmer la réservation, nous vous prions de verser un acompte de {betrag} sur le compte suivant :",
           "Merci d'effectuer le versement d'ici le {frist}.",
           "L'acompte peut également être payé par TWINT au {twint}."),
    "it": ("Per la prenotazione le chiediamo un acconto di {betrag} sul seguente conto:",
           "La preghiamo di effettuare il versamento entro il {frist}.",
           "L'acconto può essere pagato anche tramite TWINT al numero {twint}."),
    "en": ("To secure your reservation, please pay a deposit of {betrag} to the following account:",
           "Please make the payment by {frist}.",
           "You can also pay the deposit by TWINT to {twint}."),
}


_PERSONEN_WOERTER = {
    "de": (("Erwachsene/r", "Erwachsene"), ("Kind", "Kinder")),
    "fr": (("adulte", "adultes"), ("enfant", "enfants")),
    "it": (("adulto", "adulti"), ("bambino", "bambini")),
    "en": (("adult", "adults"), ("child", "children")),
}


def _kinder_total(anfrage) -> int:
    """Kinder inkl. Kleinkinder – in der Mail genügt die Gesamtzahl."""
    return (anfrage.anzahl_kinder or 0) + (getattr(anfrage, "anzahl_kleinkinder", 0) or 0)


def personen_text(erwachsene: int, kinder: int, sprache: str) -> str:
    """'2 Erwachsene, 1 Kind' – Kinder nur, wenn welche dabei sind."""
    (e1, e2), (k1, k2) = _PERSONEN_WOERTER.get(sprache, _PERSONEN_WOERTER["de"])
    text = f"{erwachsene} {e1 if erwachsene == 1 else e2}"
    if kinder:
        text += f", {kinder} {k1 if kinder == 1 else k2}"
    return text


def datum_text(d: date | None, sprache: str) -> str:
    if d is None:
        return ""
    monat = _MONATE.get(sprache, _MONATE["de"])[d.month - 1]
    return f"{d.day}. {monat} {d.year}" if sprache == "de" else f"{d.day} {monat} {d.year}"


def betrag_text(betrag: Decimal) -> str:
    """Schweizer Schreibweise: CHF 1'250.00"""
    return "CHF " + f"{betrag:,.2f}".replace(",", "'")


_ZAHLUNGSZWECK = {"de": "Zahlungszweck", "fr": "Communication", "it": "Causale", "en": "Reference"}
_NUMMER_LABEL = {"de": "Anfrage", "fr": "Demande", "it": "Richiesta", "en": "Request"}
_DANK_ANZAHLUNG = {
    "de": "Vielen Dank für Ihre Anzahlung von {betrag}, die bei uns eingegangen ist.",
    "fr": "Nous vous remercions de votre acompte de {betrag}, que nous avons bien reçu.",
    "it": "La ringraziamo per l'acconto di {betrag}, che abbiamo ricevuto.",
    "en": "Thank you for your deposit of {betrag}, which we have received.",
}


def nummer_text(nummer: str | None, sprache: str) -> str:
    return f"{_NUMMER_LABEL.get(sprache, _NUMMER_LABEL['de'])} {nummer}" if nummer else ""


def betreff_mit_nummer(betreff: str, nummer: str | None, sprache: str) -> str:
    """Hängt «[Anfrage 2026-042]» an, damit Antworten des Gastes sicher zugeordnet werden."""
    if not nummer or nummer in betreff:
        return betreff
    return f"{betreff} [{nummer_text(nummer, sprache)}]"


def zahlungsinfo(sprache: str, betrag: Decimal, frist: date | None, betrieb: dict[str, str],
                 nummer: str | None = None) -> str:
    einleitung, frist_satz, twint_satz = _ZAHLUNG.get(sprache, _ZAHLUNG["de"])
    zeilen = [einleitung.format(betrag=betrag_text(betrag))]
    konto = [f"IBAN {betrieb['iban']}" if betrieb.get("iban") else "",
             f"BIC {betrieb['bic']}" if betrieb.get("bic") else "",
             betrieb.get("kontoinhaber", ""),
             f"{_ZAHLUNGSZWECK.get(sprache, _ZAHLUNGSZWECK['de'])}: {nummer_text(nummer, sprache)}" if nummer else ""]
    zeilen += [k for k in konto if k]
    absatz = "\n".join(zeilen)
    extra = []
    if frist:
        extra.append(frist_satz.format(frist=datum_text(frist, sprache)))
    if betrieb.get("twint"):
        extra.append(twint_satz.format(twint=betrieb["twint"]))
    return absatz + ("\n\n" + "\n".join(extra) if extra else "")


def ersetze(text: str, werte: dict[str, str]) -> tuple[str, list[str]]:
    """Setzt {{platzhalter}} ein. Unbekannte bleiben stehen und werden gemeldet."""
    unbekannt: list[str] = []

    def einsetzen(m: re.Match) -> str:
        name = m[1]
        if name in werte:
            return werte[name]
        if name not in unbekannt:
            unbekannt.append(name)
        return m[0]

    ergebnis = _PLATZHALTER_RE.sub(einsetzen, text)
    ergebnis = re.sub(r"\n{3,}", "\n\n", ergebnis).strip()
    return ergebnis, unbekannt


_BETREFF_STANDARD = {
    "de": "Ihre Anfrage – Panorama-Camping Aeschi",
    "fr": "Votre demande – Panorama-Camping Aeschi",
    "it": "La sua richiesta – Panorama-Camping Aeschi",
    "en": "Your enquiry – Panorama-Camping Aeschi",
}
_ANTWORT_PRAEFIX = re.compile(r"^\s*(?:(?:re|aw|antw|wg|fw|fwd|sv|r|rif|tr)\s*(?:\[\d+\])?\s*:\s*)+", re.IGNORECASE)


def antwort_betreff(letzter_betreff: str | None, sprache: str) -> str:
    """«Re: <Betreff der letzten Gastmail>» ohne gestapelte Re:/AW:, sonst ein Standardbetreff."""
    rest = _ANTWORT_PRAEFIX.sub("", letzter_betreff or "").strip()
    rest = re.sub(r"\s*\[[^\]]*\b20\d{2}-\d{3,5}\]\s*$", "", rest)  # Nummer wird neu angehängt
    if not rest or rest.lower() in ("eingefügter mailtext",):
        return _BETREFF_STANDARD.get(sprache, _BETREFF_STANDARD["de"])
    return f"Re: {rest}"


def werte_fuer(anfrage: Reservationsanfrage, sprache: str, betrag: Decimal | None, frist: date | None,
               betrieb: dict[str, str], letzter_betreff: str | None = None,
               erhalten: Decimal | None = None, preis_pro_nacht: str = "") -> dict[str, str]:
    naechte = (anfrage.gewuenscht_bis - anfrage.gewuenscht_von).days if anfrage.gewuenscht_von and anfrage.gewuenscht_bis else ""
    return {
        "gastName": anfrage.gast_name,
        "anreise": datum_text(anfrage.gewuenscht_von, sprache),
        "abreise": datum_text(anfrage.gewuenscht_bis, sprache),
        "naechte": str(naechte),
        "stellplatzTyp": _TYPEN.get(anfrage.stellplatz_typ or "", {}).get(sprache, anfrage.stellplatz_typ or ""),
        "personen": personen_text(anfrage.anzahl_erwachsene or 0, _kinder_total(anfrage), sprache),
        "erwachsene": str(anfrage.anzahl_erwachsene or 0),
        "kinder": str(_kinder_total(anfrage)),
        "betrag": betrag_text(betrag) if betrag is not None else "",
        "zahlungsfrist": datum_text(frist, sprache),
        "zahlungsinfo": zahlungsinfo(sprache, betrag, frist, betrieb, anfrage.nummer) if betrag is not None else "",
        "antwortBetreff": antwort_betreff(letzter_betreff, sprache),
        "anfrageNummer": anfrage.nummer or "",
        "anzahlungErhalten": betrag_text(erhalten) if erhalten else "",
        "zahlungsbestaetigung": (_DANK_ANZAHLUNG.get(sprache, _DANK_ANZAHLUNG["de"]).format(betrag=betrag_text(erhalten))
                                 if erhalten else ""),
        "preisProNacht": preis_pro_nacht,
        "signatur": betrieb.get("signatur", ""),
        "infoblock": betrieb.get("infoblock", ""),
    }


def beispiel_anfrage() -> Reservationsanfrage:
    """Erfundene Anfrage für die Vorschau im Vorlagen-Editor."""
    return Reservationsanfrage(
        nummer="2027-001", gast_name="Anna Beispiel", gast_email="anna@example.ch",
        gewuenscht_von=date(2027, 7, 2), gewuenscht_bis=date(2027, 7, 5),
        stellplatz_typ="wohnwagen", anzahl_erwachsene=2, anzahl_kinder=1,
    )


def warnungen_betrieb(betrieb: dict[str, str], typ: str = TYP_ERSTANTWORT) -> list[str]:
    noetig = ("signatur", "iban") if typ == TYP_ERSTANTWORT else ("signatur",)
    fehlend = [f.bezeichnung for f in BETRIEBSFELDER if f.schluessel in noetig and not betrieb.get(f.schluessel)]
    return [f"In den Einstellungen fehlt: {', '.join(fehlend)}"] if fehlend else []


_ZAHLUNGSHINWEIS = re.compile(r"\bIBAN\b|anzahlung|deposit|acompte|acconto|caparra", re.IGNORECASE)


def ist_zahlungsantwort(text: str) -> bool:
    """Erkennt in einer ausserhalb des Tools geschriebenen Antwort die Aufforderung zur Anzahlung."""
    return bool(_ZAHLUNGSHINWEIS.search(text or ""))


def status_nach_antwort(anfrage: Reservationsanfrage, mit_anzahlung: bool) -> None:
    """
    Status nach einer gesendeten Antwort, solange die Anfrage noch in der Prüfung
    bzw. in Abklärung ist: mit Anzahlung -> «Antwort gesendet», sonst (freie
    Antwort, Rückfrage) -> «In Abklärung». Spätere Status bleiben unverändert.
    """
    from app.services.anfrage_pruefung import PRUEF_STATUS

    if anfrage.status not in PRUEF_STATUS | {"in_abklaerung"}:
        return
    if mit_anzahlung and anfrage.vollstaendig:
        anfrage.status = "erstantwort_gesendet"
    elif not mit_anzahlung:
        anfrage.status = "in_abklaerung"


def letzter_gast_betreff(db: Session, anfrage: Reservationsanfrage) -> str | None:
    """Betreff der letzten Mail des Gastes (Postfach), sonst aus dem Originaltext der Anfrage."""
    from app.models.kommunikation import MailNachricht

    n = db.execute(
        select(MailNachricht).where(MailNachricht.reservationsanfrage_id == anfrage.id, MailNachricht.richtung == "eingang")
        .order_by(MailNachricht.datum.desc())
    ).scalars().first()
    if n and n.betreff:
        return n.betreff
    erste = (anfrage.rohtext or "").split("\n", 1)[0]
    return erste[len("Betreff:"):].strip() if erste.startswith("Betreff:") else None
