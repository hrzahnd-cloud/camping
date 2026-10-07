"""Tests für die Übernahme von Reservationsanfragen aus E-Mails."""
from datetime import date, datetime, timezone
from email.message import EmailMessage

from app.models.reservation import Reservationsanfrage
from app.services.mail_import import importiere_mail, parse_reservationsmail

EINGANG = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)


def _mail(body, von="Anna Muster <anna@example.ch>", betreff="Anfrage", message_id="<a1@example.ch>", **header):
    msg = EmailMessage()
    msg["From"] = von
    msg["To"] = "info@camping-aeschi.ch"
    msg["Subject"] = betreff
    msg["Date"] = "Sun, 01 Mar 2026 10:00:00 +0000"
    if message_id:
        msg["Message-ID"] = message_id
    for name, wert in header.items():
        msg[name.replace("_", "-")] = wert
    msg.set_content(body)
    return msg


def test_deutsche_mail_wird_vollstaendig_erkannt():
    parsed = parse_reservationsmail(_mail(
        "Guten Tag, wir möchten vom 15.7.2026 bis 20.7.2026 mit 2 Erwachsenen und 3 Kindern "
        "ein Zelt reservieren. Tel: 079 123 45 67. Freundliche Grüsse, Anna"
    ))
    assert parsed.gast_name == "Anna Muster"
    assert parsed.gast_email == "anna@example.ch"
    assert parsed.gewuenscht_von == date(2026, 7, 15)
    assert parsed.gewuenscht_bis == date(2026, 7, 20)
    assert (parsed.anzahl_erwachsene, parsed.anzahl_kinder) == (2, 3)
    assert parsed.stellplatz_typ == "zeltwiese"
    assert parsed.gast_telefon == "079 123 45 67"
    assert parsed.sprache == "de"


def test_datum_ohne_jahr_nimmt_naechstes_passendes_jahr():
    parsed = parse_reservationsmail(_mail("Wir kommen vom 15.7. bis 20.7. mit dem Wohnwagen, 2 Personen."))
    assert (parsed.gewuenscht_von, parsed.gewuenscht_bis) == (date(2026, 7, 15), date(2026, 7, 20))
    assert parsed.stellplatz_typ == "wohnwagen"
    assert parsed.anzahl_erwachsene == 2


def test_jahreswechsel_ohne_jahr():
    mail = _mail("Camper, 2 Erwachsene, 28.12. bis 3.1.")
    mail.replace_header("Date", "Sun, 01 Nov 2026 10:00:00 +0000")
    parsed = parse_reservationsmail(mail)
    assert (parsed.gewuenscht_von, parsed.gewuenscht_bis) == (date(2026, 12, 28), date(2027, 1, 3))


def test_franzoesische_mail():
    parsed = parse_reservationsmail(_mail(
        "Bonjour, nous voudrions réserver un emplacement pour un camping-car du 10.08.2026 "
        "au 14.08.2026 pour 2 adultes. Merci, cordialement"
    ))
    assert parsed.sprache == "fr"
    assert parsed.stellplatz_typ == "camper"
    assert parsed.anzahl_erwachsene == 2


def test_zahlwoerter_und_reply_to():
    parsed = parse_reservationsmail(_mail(
        "Wir sind zwei Erwachsene und ein Kind, Zelt, 1.8.2026 - 5.8.2026.",
        Reply_To="Buchung <buchung@example.org>",
    ))
    assert parsed.gast_email == "buchung@example.org"
    assert (parsed.anzahl_erwachsene, parsed.anzahl_kinder) == (2, 1)


def test_html_mail_wird_in_text_umgewandelt():
    msg = EmailMessage()
    msg["From"] = "hans@example.ch"
    msg["Subject"] = "Platz"
    msg["Message-ID"] = "<h1@example.ch>"
    msg.set_content("<html><body><p>Zelt vom 1.8.2026 bis 3.8.2026</p><p>2 Erwachsene</p></body></html>", subtype="html")
    parsed = parse_reservationsmail(msg)
    assert parsed.gewuenscht_von == date(2026, 8, 1)
    assert parsed.anzahl_erwachsene == 2
    assert parsed.gast_name == "Hans"


def test_automatische_mails_werden_uebersprungen():
    assert parse_reservationsmail(_mail("Abwesend bis 5.8.", Auto_Submitted="auto-replied")) is None
    assert parse_reservationsmail(_mail("Bounce", von="MAILER-DAEMON@example.ch")) is None


def test_unvollstaendige_anfrage_wird_gespeichert_und_markiert(db):
    anfrage, art = importiere_mail(db, _mail("Habt ihr im Sommer noch Platz für uns?"))
    assert art == "neu"
    assert anfrage.vollstaendig is False
    assert anfrage.status == "unvollstaendig"
    assert "zeitraum" in anfrage.fehlende_angaben
    assert anfrage.gewuenscht_von is None
    assert "Habt ihr im Sommer" in anfrage.rohtext


def test_doppelter_import_wird_erkannt(db):
    mail = _mail("Zelt, 1.8.2026 bis 3.8.2026, 2 Erwachsene")
    assert importiere_mail(db, mail)[1] == "neu"
    assert importiere_mail(db, mail)[1] == "duplikat"
    assert db.query(Reservationsanfrage).count() == 1


def test_vollstaendige_mail_ist_geprueft(db):
    anfrage, _ = importiere_mail(db, _mail("Zelt, 1.8.2026 bis 3.8.2026, 2 Erwachsene"))
    assert anfrage.vollstaendig is True
    assert anfrage.status == "geprueft_vollstaendig"
    assert anfrage.quelle == "email"


def test_eml_endpoint(client):
    roh = _mail("Wohnwagen, 1.8.2026 bis 3.8.2026, 2 Erwachsene").as_bytes()
    antwort = client.post("/reservationsanfragen/mail-import/eml", content=roh)
    assert antwort.status_code == 201
    assert antwort.json()["stellplatz_typ"] == "wohnwagen"
    assert client.post("/reservationsanfragen/mail-import/eml", content=roh).status_code == 409
    assert client.post("/reservationsanfragen/mail-import/eml", content=b"").status_code == 400


def test_postfach_import_ohne_zugangsdaten_meldet_503(client):
    assert client.post("/reservationsanfragen/mail-import").status_code == 503
