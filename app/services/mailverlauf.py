"""
Mails aus dem Tool-Postfach einordnen (Weiterleiten/Umleiten aus dem Mailkonto
des Campingplatzes).

Jede abgerufene Mail wird zuerst «ausgepackt», falls sie weitergeleitet wurde
(Gmail, Outlook, Apple Mail, Thunderbird – im Text oder als Anhang). Danach:

1. Mail vom Homepage-Formular            -> neue Reservationsanfrage
2. Absender ist eine eigene Adresse       -> Antwort an den Gast: der passenden
   (MAIL_EIGENE_ADRESSEN, z.B. info@…)       Anfrage zuordnen, Status «Antwort
                                             gesendet»
3. Antwort des Gastes auf bestehende Mail -> der Anfrage zuordnen, als «neu»
   (Mail-Verweise oder «Re:/AW:» + Absender)  markieren
4. sonst                                  -> neue Reservationsanfrage

Umgeleitete Mails («Umleiten»/Redirect) behalten den Gast als Absender und
brauchen kein Auspacken.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email import message_from_bytes, policy
from email.message import EmailMessage
from email.utils import getaddresses, parseaddr, parsedate_to_datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.einstellungen import AppEinstellung
from app.models.kommunikation import EmailVersand, MailNachricht
from app.models.reservation import Reservationsanfrage, NUMMER_RE
from app.services import mail_import as mi
from app.services.antwortmail import ist_zahlungsantwort, status_nach_antwort

MAX_TEXT = 20000

# --- Weiterleitung erkennen -----------------------------------------------------

_MARKER = re.compile(
    r"^[ \t>]*(?:"
    r"-{2,}\s*(?:Forwarded message|Weitergeleitete Nachricht|Original Message|Ursprüngliche Nachricht|"
    r"Message transféré|Message d'origine|Messaggio inoltrato|Messaggio originale)\s*-{2,}"
    r"|(?:Begin forwarded message|Anfang der weitergeleiteten Nachricht|Début du message réexpédié|"
    r"Inizio messaggio inoltrato)\s*:"
    r"|_{20,}"
    r")[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)
_KOPF_FELDER = {
    "von": "von", "from": "von", "de": "von", "da": "von",
    "datum": "datum", "date": "datum", "gesendet": "datum", "sent": "datum", "envoyé": "datum", "inviato": "datum",
    "betreff": "betreff", "subject": "betreff", "objet": "betreff", "oggetto": "betreff",
    "an": "an", "to": "an", "à": "an", "a": "an",
    "cc": "cc", "kopie": "cc", "antwort an": "reply", "reply-to": "reply",
}
_KOPF_ZEILE = re.compile(r"^[ \t>*]*([A-Za-zÀ-ÿ\- ]{1,12})[ \t*]*:[ \t]*(.*)$")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_ANTWORT_BETREFF = re.compile(r"^\s*(?:re|aw|antw|wg|sv|r|rif|ref)\s*(?:\[\d+\])?\s*:", re.IGNORECASE)

_MONATE = {
    "jan": 1, "januar": 1, "january": 1, "janvier": 1, "gennaio": 1,
    "feb": 2, "februar": 2, "february": 2, "février": 2, "fev": 2, "febbraio": 2,
    "mär": 3, "mrz": 3, "märz": 3, "mar": 3, "march": 3, "mars": 3, "marzo": 3,
    "apr": 4, "april": 4, "avril": 4, "aprile": 4,
    "mai": 5, "may": 5, "maggio": 5,
    "jun": 6, "juni": 6, "june": 6, "juin": 6, "giugno": 6,
    "jul": 7, "juli": 7, "july": 7, "juillet": 7, "luglio": 7,
    "aug": 8, "august": 8, "août": 8, "agosto": 8,
    "sep": 9, "sept": 9, "september": 9, "septembre": 9, "settembre": 9,
    "okt": 10, "oct": 10, "oktober": 10, "october": 10, "octobre": 10, "ottobre": 10,
    "nov": 11, "november": 11, "novembre": 11,
    "dez": 12, "dec": 12, "dezember": 12, "december": 12, "décembre": 12, "dicembre": 12,
}


@dataclass
class Mail:
    """Eine (ggf. ausgepackte) Mail in vereinfachter Form."""
    von_name: str
    von: str
    an: list[str]
    betreff: str
    text: str
    datum: datetime
    message_id: str | None = None
    in_reply_to: str | None = None
    verweise: list[str] = field(default_factory=list)
    weitergeleitet: bool = False


def _datum_aus_text(wert: str, ersatz: datetime) -> datetime:
    wert = (wert or "").strip()
    if not wert:
        return ersatz
    try:
        d = parsedate_to_datetime(wert)
        return d if d.tzinfo else d.replace(tzinfo=ersatz.tzinfo or timezone.utc)
    except (TypeError, ValueError, IndexError):
        pass
    zeit = re.search(r"(\d{1,2})[:.](\d{2})(?!\d)", wert.split(" um ")[-1] if " um " in wert else wert[-12:])
    h, m = (int(zeit[1]), int(zeit[2])) if zeit else (0, 0)
    if (z := re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})", wert)):
        tag, monat, jahr = int(z[1]), int(z[2]), int(z[3])
    elif (z := re.search(r"(\d{1,2})\.?\s+([A-Za-zÀ-ÿ]+)\.?\s+(\d{4})", wert)) and z[2].lower() in _MONATE:
        tag, monat, jahr = int(z[1]), _MONATE[z[2].lower()], int(z[3])
    elif (z := re.search(r"([A-Za-z]+)\.?\s+(\d{1,2}),?\s+(\d{4})", wert)) and z[1].lower() in _MONATE:
        tag, monat, jahr = int(z[2]), _MONATE[z[1].lower()], int(z[3])
    else:
        return ersatz
    try:
        return datetime(jahr + 2000 if jahr < 100 else jahr, monat, tag, h, m, tzinfo=ersatz.tzinfo or timezone.utc)
    except ValueError:
        return ersatz


def _adressen(wert: str | None) -> list[str]:
    if not wert:
        return []
    gefunden = [a.lower() for _, a in getaddresses([wert.replace("[mailto:", "<").replace("]", ">")]) if "@" in a]
    return gefunden or [a.lower() for a in _EMAIL.findall(wert)]


def _name_und_adresse(wert: str) -> tuple[str, str]:
    wert = wert.replace("[mailto:", "<").replace("]", ">")
    name, adresse = parseaddr(wert)
    if "@" not in adresse:
        treffer = _EMAIL.search(wert)
        adresse = treffer[0] if treffer else ""
        name = wert.replace(adresse, "").strip(" <>\"'")
    return name.strip().strip('"'), adresse.lower()


def _aus_message(msg: EmailMessage, weitergeleitet: bool = False) -> Mail:
    name, adresse = _name_und_adresse(str(msg.get("From") or ""))
    try:
        datum = parsedate_to_datetime(str(msg["Date"])) if msg["Date"] else None
    except (TypeError, ValueError):
        datum = None
    datum = datum or datetime.now(timezone.utc)
    if datum.tzinfo is None:
        datum = datum.replace(tzinfo=timezone.utc)
    return Mail(
        von_name=name, von=adresse,
        an=_adressen(", ".join(str(msg.get(k) or "") for k in ("To", "Cc"))),
        betreff=str(msg.get("Subject") or ""),
        text=mi._body_text(msg)[:MAX_TEXT],
        datum=datum,
        message_id=(str(msg.get("Message-ID") or "").strip() or None),
        in_reply_to=(str(msg.get("In-Reply-To") or "").strip() or None),
        verweise=str(msg.get("References") or "").split(),
        weitergeleitet=weitergeleitet,
    )


def _inline_weiterleitung(text: str, ersatz: datetime) -> Mail | None:
    """Sucht im Text einen Weiterleitungsblock und liest dessen Kopfzeilen."""
    for treffer in _MARKER.finditer(text):
        zeilen = text[treffer.end():].lstrip("\n").splitlines()
        kopf: dict[str, str] = {}
        letzter = None
        i = 0
        while i < len(zeilen):
            zeile = zeilen[i].rstrip()
            if not zeile.strip():
                if kopf:
                    break
                i += 1
                continue
            m = _KOPF_ZEILE.match(zeile)
            schluessel = _KOPF_FELDER.get(m[1].strip().lower()) if m else None
            if schluessel:
                kopf[schluessel] = m[2].strip()
                letzter = schluessel
            elif kopf and letzter in ("an", "cc"):
                kopf[letzter] += " " + zeile.strip()   # umbrochene Empfängerliste
            else:
                break
            i += 1
        if "von" not in kopf or ("betreff" not in kopf and "datum" not in kopf):
            continue
        name, adresse = _name_und_adresse(kopf["von"])
        if not adresse:
            continue
        rumpf = "\n".join(z[1:].lstrip() if z.startswith(">") else z for z in zeilen[i:]).strip()
        return Mail(
            von_name=name, von=adresse, an=_adressen(kopf.get("an", "")),
            betreff=kopf.get("betreff", ""), text=rumpf[:MAX_TEXT],
            datum=_datum_aus_text(kopf.get("datum", ""), ersatz), weitergeleitet=True,
        )
    return None


def auspacken(msg: EmailMessage) -> Mail:
    """Die ursprüngliche Mail, falls weitergeleitet (als Anhang oder im Text), sonst die Mail selbst."""
    for teil in msg.walk():
        if teil.get_content_type() == "message/rfc822":
            innen = teil.get_content()
            if isinstance(innen, EmailMessage) and innen.get("From"):
                return _aus_message(innen, weitergeleitet=True)
    aussen = _aus_message(msg)
    innen = _inline_weiterleitung(aussen.text, aussen.datum)
    return innen or aussen


# --- Einordnen und speichern ----------------------------------------------------

def eigene_adressen(settings: Settings) -> set[str]:
    adressen = {a.strip().lower() for a in (settings.mail_eigene_adressen or "").split(",") if "@" in a}
    for weitere in (settings.smtp_absender, settings.imap_user):
        if weitere and "@" in weitere:
            adressen.add(weitere.strip().lower())
    return adressen


def _kennung(mail: Mail) -> str:
    if mail.message_id:
        return mail.message_id[:255]
    roh = f"{mail.von}|{mail.datum.isoformat()}|{mail.betreff}|{mail.text[:4000]}"
    return "sha256:" + hashlib.sha256(roh.encode()).hexdigest()


def _schon_vorhanden(db: Session, kennung: str) -> bool:
    return bool(
        db.scalar(select(func.count()).select_from(MailNachricht).where(MailNachricht.message_id == kennung))
        or db.scalar(select(func.count()).select_from(Reservationsanfrage)
                     .where(Reservationsanfrage.mail_message_id == kennung))
    )


def _durch_verweise(db: Session, mail: Mail) -> Reservationsanfrage | None:
    ids = [i for i in [mail.in_reply_to, *mail.verweise] if i]
    if not ids:
        return None
    nachricht = db.execute(
        select(MailNachricht).where(MailNachricht.message_id.in_(ids), MailNachricht.reservationsanfrage_id.is_not(None))
    ).scalars().first()
    if nachricht:
        return db.get(Reservationsanfrage, nachricht.reservationsanfrage_id)
    return db.execute(select(Reservationsanfrage).where(Reservationsanfrage.mail_message_id.in_(ids))).scalars().first()


def _durch_nummer(db: Session, betreff: str) -> Reservationsanfrage | None:
    """Anfragenummer im Betreff (z.B. «Re: … [Anfrage 2026-042]») – übersteht auch Weiterleitungen."""
    for nummer in NUMMER_RE.findall(betreff or ""):
        anfrage = db.execute(select(Reservationsanfrage).where(Reservationsanfrage.nummer == nummer)).scalars().first()
        if anfrage:
            return anfrage
    return None


def _durch_gast(db: Session, adressen: list[str]) -> Reservationsanfrage | None:
    if not adressen:
        return None
    return db.execute(
        select(Reservationsanfrage)
        .where(func.lower(Reservationsanfrage.gast_email).in_(adressen),
               Reservationsanfrage.status.not_in(("abgelehnt", "storniert")))
        .order_by(Reservationsanfrage.eingangs_datum.desc())
    ).scalars().first()


def _schon_im_tool_protokolliert(db: Session, anfrage: Reservationsanfrage, mail: Mail) -> bool:
    """Antwort wurde im Tool vorbereitet und «als gesendet markiert» – BCC-Kopie nicht doppelt führen."""
    for v in db.execute(select(EmailVersand).where(EmailVersand.bezug_typ == "reservationsanfrage",
                                                   EmailVersand.bezug_id == anfrage.id)).scalars():
        gesendet = v.gesendet_am if v.gesendet_am.tzinfo else v.gesendet_am.replace(tzinfo=timezone.utc)
        if v.betreff_final.strip() == mail.betreff.strip() and abs(gesendet - mail.datum) < timedelta(days=2):
            return True
    return False


def _speichern(db: Session, mail: Mail, kennung: str, richtung: str,
               anfrage: Reservationsanfrage | None, gelesen: bool) -> MailNachricht:
    nachricht = MailNachricht(
        reservationsanfrage_id=anfrage.id if anfrage else None, richtung=richtung, message_id=kennung,
        in_reply_to=mail.in_reply_to, verweise=" ".join(mail.verweise) or None,
        von=(f"{mail.von_name} <{mail.von}>" if mail.von_name else mail.von)[:255],
        an=", ".join(mail.an)[:500] or None, betreff=mail.betreff[:300], text=mail.text,
        datum=mail.datum.astimezone(timezone.utc), weitergeleitet=mail.weitergeleitet, gelesen=gelesen,
    )
    db.add(nachricht)
    return nachricht


def _neue_anfrage(db: Session, mail: Mail, kennung: str) -> Reservationsanfrage | None:
    original = EmailMessage()
    original["From"] = f'"{mail.von_name}" <{mail.von}>' if mail.von_name else mail.von
    original["Subject"] = mail.betreff
    original["Date"] = mail.datum.strftime("%a, %d %b %Y %H:%M:%S %z")
    original["Message-ID"] = kennung
    original.set_content(mail.text or " ")
    parsed = mi.parse_reservationsmail(original)
    if parsed is None:
        return None
    if mail.weitergeleitet:
        parsed.rohtext = "(weitergeleitet)\n" + parsed.rohtext
    anfrage = mi.speichere_anfrage(db, parsed)
    if anfrage:
        _speichern(db, mail, kennung, "eingang", anfrage, True)
        db.commit()
    return anfrage


BFS_DOMAIN = "bfs.admin.ch"


def ist_bfs_mail(absender: str, betreff: str) -> bool:
    """Mails des Bundesamts für Statistik zur HESTA (z.B. monatliche Zugangsdaten)."""
    absender = (absender or "").lower()
    return absender.endswith("@" + BFS_DOMAIN) or absender.endswith("." + BFS_DOMAIN)


_KOPF = re.compile(r"^(von|from|betreff|subject|datum|date|gesendet|sent|an|to)\s*:\s*(.*)$", re.IGNORECASE)


def bfs_mail_speichern(db: Session, text: str, betreff: str | None = None) -> MailNachricht:
    """Von Hand eingefügte BFS-Mail ablegen; Kopfzeilen (Von:, Betreff:, Datum:) werden erkannt."""
    from zoneinfo import ZoneInfo
    jetzt = datetime.now(ZoneInfo("Europe/Zurich"))  # Zeiten ohne Zone im Mailtext sind Schweizer Zeit
    von, datum, gefunden_betreff = "", jetzt, None
    for zeile in text.strip().splitlines()[:12]:
        m = _KOPF.match(zeile.strip())
        if not m:
            continue
        feld, wert = m[1].lower(), m[2].strip()
        if feld in ("von", "from") and not von:
            von = wert
        elif feld in ("betreff", "subject") and not gefunden_betreff:
            gefunden_betreff = wert
        elif feld in ("datum", "date", "gesendet", "sent"):
            datum = _datum_aus_text(wert, jetzt)
    kennung = "hesta-eingefuegt:" + hashlib.sha256(text.strip().encode()).hexdigest()[:40]
    vorhanden = db.execute(select(MailNachricht).where(MailNachricht.message_id == kennung)).scalars().first()
    if vorhanden:
        return vorhanden
    nachricht = MailNachricht(richtung="eingang", message_id=kennung, von=(von or "BFS (eingefügt)")[:255],
                              betreff=(betreff or gefunden_betreff or "HESTA – Zugangsdaten")[:300], text=text.strip(),
                              datum=datum, weitergeleitet=False, gelesen=True, kategorie="hesta")
    db.add(nachricht)
    db.commit()
    db.refresh(nachricht)
    return nachricht


def verarbeite_mail(db: Session, raw: bytes | EmailMessage, settings: Settings) -> tuple[str, Reservationsanfrage | None]:
    """
    Ordnet eine Mail ein und speichert sie.
    Ergebnis: neu | nachtrag | antwort | nicht_zugeordnet | duplikat | uebersprungen | hesta
    """
    msg = raw if isinstance(raw, EmailMessage) else message_from_bytes(raw, policy=policy.default)
    # 0. Mail des BFS (HESTA-Zugangsdaten): ins Modul HESTA, nicht zu den Reservationen.
    #    Vor dem Filter für automatische Mails, weil das BFS oft von no-reply-Adressen schickt.
    if ist_bfs_mail(parseaddr(str(msg.get("From") or ""))[1], str(msg.get("Subject") or "")):
        mail = auspacken(msg)
        kennung = _kennung(mail)
        if _schon_vorhanden(db, kennung):
            return "duplikat", None
        _speichern(db, mail, kennung, "eingang", None, False).kategorie = "hesta"
        db.commit()
        return "hesta", None
    if mi.ist_automatische_mail(msg):
        return "uebersprungen", None
    mail = auspacken(msg)
    if not mail.von:
        return "uebersprungen", None
    kennung = _kennung(mail)
    if _schon_vorhanden(db, kennung):
        return "duplikat", None

    # 1. Homepage-Formular: immer eine neue Anfrage (Absender kann auch info@ sein)
    if mi.parse_formular(mail.text):
        anfrage = _neue_anfrage(db, mail, kennung)
        return ("neu", anfrage) if anfrage else ("duplikat", None)

    # 2. Eigene Antwort an den Gast
    if mail.von in eigene_adressen(settings):
        anfrage = _durch_nummer(db, mail.betreff) or _durch_verweise(db, mail) or _durch_gast(db, mail.an)
        if anfrage and _schon_im_tool_protokolliert(db, anfrage, mail):
            return "duplikat", anfrage
        _speichern(db, mail, kennung, "ausgang", anfrage, True)
        if anfrage:
            status_nach_antwort(anfrage, ist_zahlungsantwort(mail.text))
        db.commit()
        return ("antwort", anfrage) if anfrage else ("nicht_zugeordnet", None)

    # 3. Antwort des Gastes auf eine bestehende Anfrage
    anfrage = _durch_nummer(db, mail.betreff) or _durch_verweise(db, mail)
    if anfrage is None and _ANTWORT_BETREFF.match(mail.betreff):
        anfrage = _durch_gast(db, [mail.von])
    if anfrage:
        _speichern(db, mail, kennung, "eingang", anfrage, False)
        db.commit()
        return "nachtrag", anfrage

    # 4. Neue Anfrage
    anfrage = _neue_anfrage(db, mail, kennung)
    return ("neu", anfrage) if anfrage else ("duplikat", None)


# --- Abrufprotokoll ---------------------------------------------------------------

def abruf_protokollieren(db: Session, ergebnis: dict) -> None:
    for schluessel, wert in (("mailabruf_zeit", datetime.now(timezone.utc).isoformat()),
                             ("mailabruf_ergebnis", json.dumps(ergebnis, ensure_ascii=False))):
        eintrag = db.get(AppEinstellung, schluessel)
        if eintrag is None:
            db.add(AppEinstellung(schluessel=schluessel, wert=wert))
        else:
            eintrag.wert = wert
    db.commit()


def letzter_abruf(db: Session) -> tuple[str | None, dict | None]:
    zeit = db.get(AppEinstellung, "mailabruf_zeit")
    ergebnis = db.get(AppEinstellung, "mailabruf_ergebnis")
    return (zeit.wert if zeit else None, json.loads(ergebnis.wert) if ergebnis and ergebnis.wert else None)
