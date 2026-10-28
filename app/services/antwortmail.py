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


def startvorlagen_ergaenzen(db: Session) -> int:
    """Legt fehlende Vorlagen an (idempotent). Gibt die Anzahl neuer Vorlagen zurück."""
    vorhanden = {
        v.sprache for v in db.execute(select(EmailVorlage).where(EmailVorlage.typ == TYP_ERSTANTWORT)).scalars()
    }
    neu = 0
    for sprache, (betreff, koerper) in STARTVORLAGEN.items():
        if sprache not in vorhanden:
            db.add(EmailVorlage(typ=TYP_ERSTANTWORT, sprache=sprache, betreff=betreff, koerper=koerper, aktiv=True))
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


def zahlungsinfo(sprache: str, betrag: Decimal, frist: date | None, betrieb: dict[str, str]) -> str:
    einleitung, frist_satz, twint_satz = _ZAHLUNG.get(sprache, _ZAHLUNG["de"])
    zeilen = [einleitung.format(betrag=betrag_text(betrag))]
    konto = [f"IBAN {betrieb['iban']}" if betrieb.get("iban") else "",
             f"BIC {betrieb['bic']}" if betrieb.get("bic") else "",
             betrieb.get("kontoinhaber", "")]
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


def werte_fuer(anfrage: Reservationsanfrage, sprache: str, betrag: Decimal, frist: date | None,
               betrieb: dict[str, str]) -> dict[str, str]:
    naechte = (anfrage.gewuenscht_bis - anfrage.gewuenscht_von).days if anfrage.gewuenscht_von and anfrage.gewuenscht_bis else ""
    return {
        "gastName": anfrage.gast_name,
        "anreise": datum_text(anfrage.gewuenscht_von, sprache),
        "abreise": datum_text(anfrage.gewuenscht_bis, sprache),
        "naechte": str(naechte),
        "stellplatzTyp": _TYPEN.get(anfrage.stellplatz_typ or "", {}).get(sprache, anfrage.stellplatz_typ or ""),
        "personen": personen_text(anfrage.anzahl_erwachsene or 0, anfrage.anzahl_kinder or 0, sprache),
        "erwachsene": str(anfrage.anzahl_erwachsene or 0),
        "kinder": str(anfrage.anzahl_kinder or 0),
        "betrag": betrag_text(betrag),
        "zahlungsfrist": datum_text(frist, sprache),
        "zahlungsinfo": zahlungsinfo(sprache, betrag, frist, betrieb),
        "signatur": betrieb.get("signatur", ""),
        "infoblock": betrieb.get("infoblock", ""),
    }


def beispiel_anfrage() -> Reservationsanfrage:
    """Erfundene Anfrage für die Vorschau im Vorlagen-Editor."""
    return Reservationsanfrage(
        gast_name="Anna Beispiel", gast_email="anna@example.ch",
        gewuenscht_von=date(2027, 7, 2), gewuenscht_bis=date(2027, 7, 5),
        stellplatz_typ="wohnwagen", anzahl_erwachsene=2, anzahl_kinder=1,
    )


def warnungen_betrieb(betrieb: dict[str, str]) -> list[str]:
    fehlend = [f.bezeichnung for f in BETRIEBSFELDER if f.schluessel in ("signatur", "iban") and not betrieb.get(f.schluessel)]
    return [f"In den Einstellungen fehlt: {', '.join(fehlend)}"] if fehlend else []
