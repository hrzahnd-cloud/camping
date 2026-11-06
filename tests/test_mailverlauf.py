"""
Tests: weitergeleitete/umgeleitete Mails, eigene Antworten und Rückfragen von
Gästen einordnen. Alle Personen und Adressen sind erfunden.
"""
from datetime import datetime, timezone
from email.message import EmailMessage

import pytest
from sqlalchemy import select

from app.config import Settings
from app.models.kommunikation import EmailVersand, EmailVorlage, MailNachricht
from app.models.reservation import Reservationsanfrage
from app.services.mailverlauf import auspacken, verarbeite_mail

EIGEN = "info@camping-test.ch"
EINSTELLUNGEN = Settings(_env_file=None, mail_eigene_adressen=EIGEN, smtp_absender=EIGEN)
ANFRAGE_TEXT = "Guten Tag, wir möchten vom 10.7.2027 bis 14.7.2027 mit 2 Erwachsenen und 1 Kind zelten.\nFreundliche Grüsse, Anna"


def _mail(von, betreff, text, an=EIGEN, datum="Wed, 28 Oct 2026 13:00:00 +0100", message_id=None, html=None, **kopf):
    msg = EmailMessage()
    msg["From"] = von
    msg["To"] = an
    msg["Subject"] = betreff
    msg["Date"] = datum
    if message_id:
        msg["Message-ID"] = message_id
    for k, v in kopf.items():
        msg[k.replace("_", "-")] = v
    if html is None:
        msg.set_content(text)
    else:
        msg.set_content(html, subtype="html")
    return msg


def _weiter(block):
    """Weitergeleitet vom eigenen Konto, mit kurzer Notiz davor."""
    return _mail(f"Camping Test <{EIGEN}>", "WG: Anfrage", "Bitte erfassen.\n\n" + block, an="tool@camping-test.ch")


FORMEN = {
    "gmail_de": f"""---------- Weitergeleitete Nachricht ---------
Von: Anna Muster <anna@example.ch>
Date: Mi., 28. Okt. 2026 um 12:05 Uhr
Subject: Anfrage Zelt Juli
To: <{EIGEN}>


{ANFRAGE_TEXT}""",
    "gmail_en": f"""---------- Forwarded message ---------
From: Anna Muster <anna@example.ch>
Date: Wed, 28 Oct 2026 at 12:05
Subject: Anfrage Zelt Juli
To: <{EIGEN}>

{ANFRAGE_TEXT}""",
    "outlook_klassisch": f"""-----Ursprüngliche Nachricht-----
Von: Anna Muster [mailto:anna@example.ch]
Gesendet: Mittwoch, 28. Oktober 2026 12:05
An: {EIGEN}
Betreff: Anfrage Zelt Juli

{ANFRAGE_TEXT}""",
    "outlook_neu": f"""________________________________
Von: Anna Muster <anna@example.ch>
Gesendet: Mittwoch, 28. Oktober 2026 12:05
An: Camping Test <{EIGEN}>
Betreff: Anfrage Zelt Juli

{ANFRAGE_TEXT}""",
    "apple_mail": f"""Anfang der weitergeleiteten Nachricht:

Von: Anna Muster <anna@example.ch>
Betreff: Anfrage Zelt Juli
Datum: 28. Oktober 2026 um 12:05:00 MEZ
An: {EIGEN}

{ANFRAGE_TEXT}""",
    "thunderbird": f"""-------- Weitergeleitete Nachricht --------
Betreff: \tAnfrage Zelt Juli
Datum: \tWed, 28 Oct 2026 12:05:00 +0100
Von: \tAnna Muster <anna@example.ch>
An: \t{EIGEN}

{ANFRAGE_TEXT}""",
}


@pytest.mark.parametrize("form", FORMEN)
def test_weitergeleitete_anfrage_wird_ausgepackt(db, form):
    mail = auspacken(_weiter(FORMEN[form]))
    assert (mail.von, mail.von_name, mail.betreff) == ("anna@example.ch", "Anna Muster", "Anfrage Zelt Juli")
    assert mail.weitergeleitet and mail.text.startswith("Guten Tag")
    assert (mail.datum.year, mail.datum.month, mail.datum.day, mail.datum.hour, mail.datum.minute) == (2026, 10, 28, 12, 5)

    art, anfrage = verarbeite_mail(db, _weiter(FORMEN[form]), EINSTELLUNGEN)
    assert art == "neu"
    assert anfrage.gast_email == "anna@example.ch" and anfrage.gast_name == "Anna Muster"  # nicht das eigene Konto
    assert (anfrage.anzahl_erwachsene, anfrage.stellplatz_typ, anfrage.vollstaendig) == (2, "zeltwiese", True)
    assert anfrage.rohtext.startswith("(weitergeleitet)")


def test_weitergeleitet_als_anhang(db):
    original = _mail("Anna Muster <anna@example.ch>", "Anfrage Zelt Juli", ANFRAGE_TEXT, message_id="<orig-1@example.ch>")
    huelle = _mail(EIGEN, "WG: Anfrage Zelt Juli", "Siehe Anhang", an="tool@camping-test.ch")
    huelle.add_attachment(original)
    art, anfrage = verarbeite_mail(db, huelle, EINSTELLUNGEN)
    assert art == "neu" and anfrage.gast_email == "anna@example.ch"
    assert anfrage.mail_message_id == "<orig-1@example.ch>"


def test_weitergeleitet_nur_html(db):
    html = ("<div>Bitte erfassen</div><div>---------- Forwarded message ---------<br>"
            "<b>From:</b> Anna Muster &lt;anna@example.ch&gt;<br><b>Date:</b> Wed, 28 Oct 2026 at 12:05<br>"
            "<b>Subject:</b> Anfrage Zelt Juli<br><b>To:</b> &lt;info@camping-test.ch&gt;<br><br><br>"
            "<div>" + ANFRAGE_TEXT.replace("\n", "<br>") + "</div></div>")
    art, anfrage = verarbeite_mail(db, _mail(EIGEN, "Fwd: Anfrage", "", html=html), EINSTELLUNGEN)
    assert art == "neu" and anfrage.gast_email == "anna@example.ch" and anfrage.anzahl_erwachsene == 2


def test_umgeleitete_mail_behaelt_absender(db):
    msg = _mail("Anna Muster <anna@example.ch>", "Anfrage Zelt Juli", ANFRAGE_TEXT,
                message_id="<orig-2@example.ch>", Resent_From=EIGEN, Resent_To="tool@camping-test.ch")
    art, anfrage = verarbeite_mail(db, msg, EINSTELLUNGEN)
    assert art == "neu" and anfrage.gast_email == "anna@example.ch"
    assert verarbeite_mail(db, msg, EINSTELLUNGEN)[0] == "duplikat"


def _anfrage_von_anna(db):
    art, anfrage = verarbeite_mail(db, _mail("Anna Muster <anna@example.ch>", "Anfrage Zelt Juli", ANFRAGE_TEXT,
                                             message_id="<orig-3@example.ch>"), EINSTELLUNGEN)
    assert art == "neu"
    return anfrage


def test_eigene_antwort_per_bcc_wird_zugeordnet(db):
    anfrage = _anfrage_von_anna(db)
    antwort = _mail(f"Camping Test <{EIGEN}>", "Re: Anfrage Zelt Juli", "Guten Tag Frau Muster, gerne reservieren wir ...",
                    an="anna@example.ch", message_id="<antwort-1@camping-test.ch>", In_Reply_To="<orig-3@example.ch>",
                    datum="Wed, 28 Oct 2026 15:00:00 +0100")
    art, zugeordnet = verarbeite_mail(db, antwort, EINSTELLUNGEN)
    assert art == "antwort" and zugeordnet.id == anfrage.id
    db.refresh(anfrage)
    # Antwort ohne Zahlungsangaben = freie Antwort/Rückfrage
    assert anfrage.status == "in_abklaerung"
    n = db.execute(select(MailNachricht).where(MailNachricht.richtung == "ausgang")).scalar_one()
    assert n.reservationsanfrage_id == anfrage.id and n.gelesen is True

    mit_anzahlung = _mail(f"Camping Test <{EIGEN}>", "Re: Anfrage Zelt Juli",
                          "Bitte überweisen Sie die Anzahlung von CHF 100.00 auf IBAN CH00 0000 0000 0000 0000 0.",
                          an="anna@example.ch", message_id="<antwort-2@camping-test.ch>",
                          datum="Thu, 29 Oct 2026 10:00:00 +0100")
    assert verarbeite_mail(db, mit_anzahlung, EINSTELLUNGEN)[0] == "antwort"
    db.refresh(anfrage)
    assert anfrage.status == "erstantwort_gesendet"


def test_eigene_antwort_ohne_verweise_ueber_empfaenger(db):
    anfrage = _anfrage_von_anna(db)
    art, zugeordnet = verarbeite_mail(db, _mail(EIGEN, "Ihre Reservation", "Guten Tag ...", an="Anna <ANNA@example.ch>"),
                                      EINSTELLUNGEN)
    assert art == "antwort" and zugeordnet.id == anfrage.id


def test_eigene_antwort_weitergeleitet_aus_gesendeten(db):
    anfrage = _anfrage_von_anna(db)
    block = f"""-----Ursprüngliche Nachricht-----
Von: Camping Test [mailto:{EIGEN}]
Gesendet: Mittwoch, 28. Oktober 2026 15:00
An: Anna Muster <anna@example.ch>
Betreff: Ihre Reservation vom 10. Juli 2027

Guten Tag Frau Muster ..."""
    art, zugeordnet = verarbeite_mail(db, _weiter(block), EINSTELLUNGEN)
    assert art == "antwort" and zugeordnet.id == anfrage.id


def test_bcc_kopie_einer_im_tool_vorbereiteten_antwort_nicht_doppelt(db):
    anfrage = _anfrage_von_anna(db)
    vorlage = EmailVorlage(typ="erstantwort_zahlungsinfo", sprache="de", betreff="x", koerper="x")
    db.add(vorlage)
    db.flush()
    db.add(EmailVersand(bezug_typ="reservationsanfrage", bezug_id=anfrage.id, vorlage_id=vorlage.id, gesendet_von="test",
                        empfaenger="anna@example.ch", betreff_final="Ihre Reservation vom 10. Juli 2027",
                        koerper_final="...", gesendet_am=datetime(2026, 10, 28, 14, 0, tzinfo=timezone.utc)))
    db.commit()
    art, _ = verarbeite_mail(db, _mail(EIGEN, "Ihre Reservation vom 10. Juli 2027", "...", an="anna@example.ch"), EINSTELLUNGEN)
    assert art == "duplikat"
    assert db.execute(select(MailNachricht).where(MailNachricht.richtung == "ausgang")).first() is None


def test_eigene_mail_ohne_passende_anfrage(db):
    art, anfrage = verarbeite_mail(db, _mail(EIGEN, "Info", "...", an="unbekannt@example.com"), EINSTELLUNGEN)
    assert (art, anfrage) == ("nicht_zugeordnet", None)
    assert db.execute(select(MailNachricht)).scalar_one().reservationsanfrage_id is None


def test_rueckfrage_des_gastes_per_betreff(db):
    anfrage = _anfrage_von_anna(db)
    art, zugeordnet = verarbeite_mail(db, _mail("anna@example.ch", "AW: Ihre Reservation vom 10. Juli 2027",
                                                "Vielen Dank, wir überweisen morgen."), EINSTELLUNGEN)
    assert art == "nachtrag" and zugeordnet.id == anfrage.id
    n = db.execute(select(MailNachricht).where(MailNachricht.gelesen.is_(False))).scalar_one()
    assert n.richtung == "eingang" and "überweisen" in n.text
    assert db.query(Reservationsanfrage).count() == 1  # keine zweite Anfrage


def test_rueckfrage_per_verweis_auf_eigene_antwort(db):
    anfrage = _anfrage_von_anna(db)
    verarbeite_mail(db, _mail(EIGEN, "Ihre Reservation", "...", an="anna@example.ch",
                              message_id="<antwort-2@camping-test.ch>"), EINSTELLUNGEN)
    art, zugeordnet = verarbeite_mail(db, _mail("anna.privat@example.org", "Frage", "Dürfen wir einen Hund mitnehmen?",
                                                References="<orig-3@example.ch> <antwort-2@camping-test.ch>"),
                                      EINSTELLUNGEN)
    assert art == "nachtrag" and zugeordnet.id == anfrage.id


def test_neue_mail_desselben_gastes_ohne_antwortbezug_ist_neue_anfrage(db):
    _anfrage_von_anna(db)
    art, _ = verarbeite_mail(db, _mail("anna@example.ch", "Noch eine Anfrage",
                                       "Wir möchten auch vom 1.8.2027 bis 3.8.2027 kommen, 2 Erwachsene, Wohnwagen."),
                             EINSTELLUNGEN)
    assert art == "neu"


def test_formularmail_vom_eigenen_konto_ist_neue_anfrage(db):
    from tests.test_mail_formular import FORMULAR_EN

    art, anfrage = verarbeite_mail(db, _mail(EIGEN, "Neue Reservationsanfrage", FORMULAR_EN), EINSTELLUNGEN)
    assert art == "neu" and anfrage.gast_email == "mia.beispiel@example.com" and anfrage.anzahl_erwachsene == 3


def test_abwesenheitsnotiz_wird_uebersprungen(db):
    msg = _mail("anna@example.ch", "Abwesend", "Ich bin bis 5.11. abwesend.", Auto_Submitted="auto-replied")
    assert verarbeite_mail(db, msg, EINSTELLUNGEN)[0] == "uebersprungen"


@pytest.mark.parametrize("text", [
    "Hallo, 2 Erwachsene 10.7.-12.7.\n\n____________________________\nVon: Mobile gesendet\nTelefon: 079 000 00 00",
    "Guten Tag\nDatum: 10.7.2027\nVon: Bern\nWir kommen mit Zelt.",
    "Danke!\n\nAm 28.10.2026 um 12:00 schrieb Camping <info@camping-test.ch>:\n> Guten Tag ...",
])
def test_normale_mails_gelten_nicht_als_weitergeleitet(text):
    mail = auspacken(_mail("Gast <gast@example.ch>", "Anfrage", text))
    assert mail.weitergeleitet is False and mail.von == "gast@example.ch"


def test_verlauf_gelesen_und_postfach_api(client, db):
    anfrage = _anfrage_von_anna(db)
    verarbeite_mail(db, _mail("anna@example.ch", "AW: Anfrage Zelt Juli", "Noch eine Frage zum Strom.",
                              datum="Thu, 29 Oct 2026 09:00:00 +0100"), EINSTELLUNGEN)
    verarbeite_mail(db, _mail(EIGEN, "Info", "...", an="unbekannt@example.com"), EINSTELLUNGEN)

    liste = {a["id"]: a for a in client.get("/reservationsanfragen").json()}
    assert liste[str(anfrage.id)]["neue_mails"] == 1
    verlauf = client.get(f"/reservationsanfragen/{anfrage.id}/mails").json()
    assert [(v["richtung"], v["quelle"], v["gelesen"]) for v in verlauf] == [
        ("eingang", "postfach", False), ("eingang", "postfach", True)]
    assert client.post(f"/reservationsanfragen/{anfrage.id}/mails/gelesen").status_code == 204
    assert client.get(f"/reservationsanfragen/{anfrage.id}").json()["neue_mails"] == 0

    status = client.get("/einstellungen/postfach").json()
    assert status["eingerichtet"] is False and len(status["nicht_zugeordnet"]) == 1
    offen = status["nicht_zugeordnet"][0]
    r = client.post(f"/einstellungen/postfach/mails/{offen['id']}/zuordnen", json={"anfrage_id": str(anfrage.id)})
    assert r.status_code == 200 and r.json()["nicht_zugeordnet"] == []
    assert client.get(f"/reservationsanfragen/{anfrage.id}").json()["status"] == "in_abklaerung"


def test_imap_abruf_ordnet_ein_und_protokolliert(db, monkeypatch):
    """Simulierter IMAP-Server: drei Mails (Anfrage, Antwort, Rückfrage)."""
    from app.services import mail_import as mi
    from app.services.mailverlauf import letzter_abruf

    mails = [
        _mail("Anna Muster <anna@example.ch>", "Anfrage Zelt Juli", ANFRAGE_TEXT, message_id="<imap-1@example.ch>"),
        _mail(EIGEN, "Re: Anfrage Zelt Juli", "Gerne ...", an="anna@example.ch", In_Reply_To="<imap-1@example.ch>"),
        _mail("anna@example.ch", "AW: Re: Anfrage Zelt Juli", "Danke, bezahlt."),
    ]
    markiert = []

    class FakeImap:
        def __init__(self, *a, **k): pass
        def login(self, *a): pass
        def select(self, *a): pass
        def search(self, *a): return "OK", [b"1 2 3"]
        def fetch(self, nummer, _): return "OK", [(b"x", mails[int(nummer) - 1].as_bytes())]
        def store(self, nummer, *_): markiert.append(nummer)
        def logout(self): pass

    monkeypatch.setattr(mi.imaplib, "IMAP4_SSL", FakeImap)
    settings = Settings(_env_file=None, imap_host="imap.example.ch", imap_user="tool@camping-test.ch",
                        imap_password="x", mail_eigene_adressen=EIGEN)
    e = mi.importiere_aus_postfach(db, settings)
    assert (e.neu, e.antworten, e.nachtraege, e.fehler) == (1, 1, 1, [])
    assert markiert == [b"1", b"2", b"3"]
    zeit, ergebnis = letzter_abruf(db)
    assert zeit and ergebnis["neu"] == 1 and ergebnis["nachtraege"] == 1


def test_zeiten_werden_in_utc_gespeichert(db):
    anfrage = _anfrage_von_anna(db)
    verarbeite_mail(db, _mail("anna@example.ch", "AW: Anfrage Zelt Juli", "Frage", datum="Tue, 03 Nov 2026 12:30:00 +0100"),
                    EINSTELLUNGEN)
    n = db.execute(select(MailNachricht).where(MailNachricht.gelesen.is_(False))).scalar_one()
    gespeichert = n.datum if n.datum.tzinfo else n.datum.replace(tzinfo=timezone.utc)
    assert gespeichert == datetime(2026, 11, 3, 11, 30, tzinfo=timezone.utc)
    assert anfrage.id == n.reservationsanfrage_id
