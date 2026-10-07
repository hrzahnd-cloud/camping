"""
Übernahme von Reservationsanfragen per E-Mail (Konzept Abschnitt 10).

Ablauf: Mail aus dem Postfach (IMAP) oder als .eml-Datei -> Felder per
Muster erkennen -> Reservationsanfrage speichern -> Vollständigkeit prüfen.
Was nicht sicher erkannt wird, bleibt leer; die Anfrage gilt dann als
unvollständig und wird von einer Person ergänzt. Der Originaltext bleibt
immer in `rohtext` erhalten.

Die Zugangsdaten (IMAP_*) sind noch nicht hinterlegt: ohne `imap_host`
passiert nichts. Der Parser lässt sich unabhängig davon mit .eml-Dateien
nutzen (POST /reservationsanfragen/mail-import/eml).
"""
import hashlib
import imaplib
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from email import message_from_bytes, policy
from email.message import EmailMessage
from email.utils import parseaddr, parsedate_to_datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.reservation import Reservationsanfrage
from app.services.anfrage_pruefung import wende_pruefung_an

log = logging.getLogger(__name__)

MAX_ROHTEXT = 20000

_ZAHLWOERTER = {
    "ein": 1, "eine": 1, "einen": 1, "zwei": 2, "drei": 3, "vier": 4, "fünf": 5, "fuenf": 5,
    "sechs": 6, "sieben": 7, "acht": 8, "un": 1, "deux": 2, "trois": 3, "quatre": 4,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
}
_ZAHL = r"(\d{1,2}|" + "|".join(_ZAHLWOERTER) + r")"

_ERWACHSENE = re.compile(
    _ZAHL + r"\s*(?:erwachsene[rn]?|erw\b\.?|adults?|adultes?|adulti)", re.IGNORECASE
)
_KINDER = re.compile(
    _ZAHL + r"\s*(?:kinder[n]?|kind\b|children|child\b|kids?|enfants?|bambini)", re.IGNORECASE
)
_PERSONEN = re.compile(_ZAHL + r"\s*(?:personen|person\b|people|persons|personnes|persone)", re.IGNORECASE)

# Stellplatztyp-Codes entsprechen Stellplatz.typ (siehe app/models/campingplatz.py)
_STELLPLATZ_STICHWORTE = [
    ("zwaergli", re.compile(r"zw(?:ä|ae)rgli", re.IGNORECASE)),
    ("spycher", re.compile(r"spycher", re.IGNORECASE)),
    ("wohnwagen", re.compile(r"wohnwagen|caravan|roulotte", re.IGNORECASE)),
    ("camper", re.compile(r"camper|wohnmobil|womo|motorhome|camping-car", re.IGNORECASE)),
    ("zeltwiese", re.compile(r"\bzelt|tente\b|\btent\b|tenda", re.IGNORECASE)),
]

_DATUM_PUNKT = re.compile(r"(?<!\d)(\d{1,2})\.\s?(\d{1,2})\.(?:(\d{4}|\d{2})(?!\d))?")
_DATUM_ISO = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
_TELEFON = re.compile(
    r"(?:tel(?:efon)?|mobile?|handy|natel|phone|t[eé]l[eé]phone)\.?\s*:?\s*"
    r"(\+?\d[\d\s/().-]{6,}\d)",
    re.IGNORECASE,
)

_SPRACH_WOERTER = {
    "de": ["und", "ich", "wir", "vom", "bis", "gerne", "freundliche", "grüsse", "gruss", "bitte", "platz", "personen"],
    "fr": ["bonjour", "nous", "pour", "avec", "du", "au", "cordialement", "merci", "emplacement", "personnes"],
    "it": ["buongiorno", "vorremmo", "per", "dal", "con", "grazie", "distinti", "saluti", "persone", "piazzola"],
    "en": ["hello", "we", "would", "like", "from", "to", "thank", "regards", "please", "pitch", "people"],
}


@dataclass
class ParsedAnfrage:
    gast_name: str
    gast_email: str
    eingangs_datum: datetime
    sprache: str = "de"
    gast_telefon: str | None = None
    gewuenscht_von: date | None = None
    gewuenscht_bis: date | None = None
    stellplatz_typ: str | None = None
    anzahl_erwachsene: int = 0
    anzahl_kinder: int = 0
    bemerkung: str | None = None
    rohtext: str = ""
    mail_message_id: str | None = None


@dataclass
class ImportErgebnis:
    neu: int = 0
    duplikate: int = 0
    uebersprungen: int = 0
    fehler: list[str] = field(default_factory=list)


class MailImportNichtKonfiguriert(Exception):
    """IMAP-Zugangsdaten sind (noch) nicht hinterlegt."""


def _zahl(text: str) -> int:
    t = text.lower()
    return int(t) if t.isdigit() else _ZAHLWOERTER.get(t, 0)


def _html_zu_text(html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    text = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    for alt, neu in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"')):
        text = text.replace(alt, neu)
    return re.sub(r"[ \t]+", " ", text)


def _body_text(msg: EmailMessage) -> str:
    body = msg.get_body(preferencelist=("plain", "html"))
    if body is None:
        return ""
    inhalt = body.get_content()
    if body.get_content_type() == "text/html":
        inhalt = _html_zu_text(inhalt)
    return inhalt.strip()


def _erkenne_daten(text: str, bezug: date) -> tuple[date | None, date | None]:
    """Erste zwei plausible Datumsangaben als (von, bis); fehlendes Jahr wird ergänzt."""
    kandidaten: list[tuple[int, date | None, int, int, int | None]] = []
    for m in _DATUM_ISO.finditer(text):
        try:
            kandidaten.append((m.start(), date(int(m[1]), int(m[2]), int(m[3])), 0, 0, None))
        except ValueError:
            continue
    for m in _DATUM_PUNKT.finditer(text):
        tag, monat = int(m[1]), int(m[2])
        if not (1 <= tag <= 31 and 1 <= monat <= 12):
            continue
        jahr = int(m[3]) if m[3] else None
        if jahr is not None and jahr < 100:
            jahr += 2000
        if jahr is not None:
            try:
                kandidaten.append((m.start(), date(jahr, monat, tag), tag, monat, jahr))
            except ValueError:
                continue
        else:
            kandidaten.append((m.start(), None, tag, monat, None))
    kandidaten.sort(key=lambda k: k[0])

    ergebnis: list[date] = []
    for _, d, tag, monat, jahr in kandidaten:
        if len(ergebnis) == 2:
            break
        if d is None:
            basis = ergebnis[-1] if ergebnis else bezug
            for j in (basis.year, basis.year + 1):
                try:
                    d = date(j, monat, tag)
                except ValueError:
                    break
                if d >= (ergebnis[-1] if ergebnis else bezug):
                    break
            if d is None:
                continue
        ergebnis.append(d)

    von = ergebnis[0] if len(ergebnis) > 0 else None
    bis = ergebnis[1] if len(ergebnis) > 1 else None
    return von, bis


def _erkenne_personen(text: str) -> tuple[int, int]:
    erw = sum(_zahl(m[1]) for m in _ERWACHSENE.finditer(text))
    kinder = sum(_zahl(m[1]) for m in _KINDER.finditer(text))
    if erw == 0:
        gesamt = sum(_zahl(m[1]) for m in _PERSONEN.finditer(text))
        erw = max(gesamt - kinder, 0)
    return erw, kinder


def _erkenne_stellplatz(text: str) -> str | None:
    beste: tuple[int, str] | None = None
    for code, muster in _STELLPLATZ_STICHWORTE:
        m = muster.search(text)
        if m and (beste is None or m.start() < beste[0]):
            beste = (m.start(), code)
    return beste[1] if beste else None


def _erkenne_sprache(text: str) -> str:
    woerter = set(re.findall(r"[a-zäöüéèàç]+", text.lower()))
    punkte = {s: len(woerter & set(liste)) for s, liste in _SPRACH_WOERTER.items()}
    sprache, treffer = max(punkte.items(), key=lambda kv: kv[1])
    return sprache if treffer >= 2 else "de"


def ist_automatische_mail(msg: EmailMessage) -> bool:
    """Bounces, Abwesenheitsnotizen und Newsletter werden nicht importiert."""
    auto = (msg.get("Auto-Submitted") or "").lower()
    if auto and auto != "no":
        return True
    if (msg.get("Precedence") or "").lower() in ("bulk", "junk", "list"):
        return True
    absender = parseaddr(str(msg.get("From") or ""))[1].lower()
    return absender.startswith(("mailer-daemon@", "postmaster@", "no-reply@", "noreply@"))


def parse_reservationsmail(raw: bytes | EmailMessage, jetzt: datetime | None = None) -> ParsedAnfrage | None:
    """Liest eine Mail und gibt die erkannten Anfragedaten zurück (None bei automatischen Mails)."""
    msg = raw if isinstance(raw, EmailMessage) else message_from_bytes(raw, policy=policy.default)
    if ist_automatische_mail(msg):
        return None

    name, adresse = parseaddr(str(msg.get("Reply-To") or msg.get("From") or ""))
    if not adresse:
        return None
    if not name:
        lokal = adresse.split("@")[0]
        name = re.sub(r"[._-]+", " ", lokal).title()

    try:
        eingang = parsedate_to_datetime(str(msg["Date"])) if msg["Date"] else None
    except (TypeError, ValueError):
        eingang = None
    eingang = eingang or jetzt or datetime.now(timezone.utc)
    if eingang.tzinfo is None:
        eingang = eingang.replace(tzinfo=timezone.utc)

    betreff = str(msg.get("Subject") or "")
    text = _body_text(msg)
    volltext = f"{betreff}\n{text}"

    von, bis = _erkenne_daten(volltext, eingang.date())
    erw, kinder = _erkenne_personen(volltext)
    telefon = _TELEFON.search(volltext)

    message_id = (msg.get("Message-ID") or "").strip() or None
    if message_id is None:
        digest = hashlib.sha256(f"{adresse}|{eingang.isoformat()}|{volltext}".encode()).hexdigest()
        message_id = f"sha256:{digest}"

    return ParsedAnfrage(
        gast_name=name.strip()[:200],
        gast_email=adresse.strip()[:255],
        eingangs_datum=eingang,
        sprache=_erkenne_sprache(volltext),
        gast_telefon=re.sub(r"\s+", " ", telefon[1]).strip()[:50] if telefon else None,
        gewuenscht_von=von,
        gewuenscht_bis=bis,
        stellplatz_typ=_erkenne_stellplatz(volltext),
        anzahl_erwachsene=erw,
        anzahl_kinder=kinder,
        rohtext=f"Betreff: {betreff}\n\n{text}"[:MAX_ROHTEXT],
        mail_message_id=message_id[:255],
    )


def speichere_anfrage(db: Session, parsed: ParsedAnfrage) -> Reservationsanfrage | None:
    """Legt die Anfrage an; gibt None zurück, wenn die Mail schon importiert wurde."""
    vorhanden = db.execute(
        select(Reservationsanfrage.id).where(Reservationsanfrage.mail_message_id == parsed.mail_message_id)
    ).first()
    if vorhanden:
        return None

    anfrage = Reservationsanfrage(
        quelle="email",
        eingangs_datum=parsed.eingangs_datum,
        sprache=parsed.sprache,
        gast_name=parsed.gast_name,
        gast_email=parsed.gast_email,
        gast_telefon=parsed.gast_telefon,
        gewuenscht_von=parsed.gewuenscht_von,
        gewuenscht_bis=parsed.gewuenscht_bis,
        stellplatz_typ=parsed.stellplatz_typ,
        anzahl_erwachsene=parsed.anzahl_erwachsene,
        anzahl_kinder=parsed.anzahl_kinder,
        rohtext=parsed.rohtext,
        mail_message_id=parsed.mail_message_id,
        newsletter_einwilligung=False,
    )
    wende_pruefung_an(anfrage)
    db.add(anfrage)
    db.commit()
    db.refresh(anfrage)
    return anfrage


def importiere_mail(db: Session, raw: bytes | EmailMessage) -> tuple[Reservationsanfrage | None, str]:
    """Parst und speichert eine Mail. Status: 'neu' | 'duplikat' | 'uebersprungen'."""
    parsed = parse_reservationsmail(raw)
    if parsed is None:
        return None, "uebersprungen"
    anfrage = speichere_anfrage(db, parsed)
    return (anfrage, "neu") if anfrage else (None, "duplikat")


def imap_konfiguriert(settings: Settings) -> bool:
    return bool(settings.imap_host and settings.imap_user and settings.imap_password)


def importiere_aus_postfach(db: Session, settings: Settings, max_mails: int = 50) -> ImportErgebnis:
    """Holt ungelesene Mails per IMAP und importiert sie; erst nach dem Speichern als gelesen markieren."""
    if not imap_konfiguriert(settings):
        raise MailImportNichtKonfiguriert("IMAP_HOST, IMAP_USER und IMAP_PASSWORD sind nicht gesetzt.")

    ergebnis = ImportErgebnis()
    verbindung = imaplib.IMAP4_SSL(settings.imap_host, settings.imap_port, timeout=30)
    try:
        verbindung.login(settings.imap_user, settings.imap_password)
        verbindung.select(settings.imap_ordner)
        status, daten = verbindung.search(None, "UNSEEN")
        if status != "OK":
            ergebnis.fehler.append(f"IMAP-Suche fehlgeschlagen: {status}")
            return ergebnis

        for nummer in daten[0].split()[:max_mails]:
            try:
                status, teile = verbindung.fetch(nummer, "(BODY.PEEK[])")
                if status != "OK" or not teile or not isinstance(teile[0], tuple):
                    ergebnis.fehler.append(f"Mail {nummer.decode()}: Abruf fehlgeschlagen")
                    continue
                _, art = importiere_mail(db, teile[0][1])
                if art == "neu":
                    ergebnis.neu += 1
                elif art == "duplikat":
                    ergebnis.duplikate += 1
                else:
                    ergebnis.uebersprungen += 1
                verbindung.store(nummer, "+FLAGS", "\\Seen")
            except Exception as exc:  # eine defekte Mail darf den Rest nicht blockieren
                db.rollback()
                log.exception("Mail-Import: Fehler bei Mail %s", nummer)
                ergebnis.fehler.append(f"Mail {nummer.decode()}: {exc}")
    finally:
        try:
            verbindung.logout()
        except Exception:
            pass
    return ergebnis
