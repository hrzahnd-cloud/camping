"""
Tests: Reservationsmails aus dem Homepage-Formular.

Alle Personen und Adressen sind erfunden; das Format entspricht den echten
Formularmails (Kopfblock ohne Feldnamen, zweisprachige Feldnamen, die über
zwei Zeilen umbrechen können).
"""
from datetime import date, datetime, timezone
from email.message import EmailMessage

from app.services.mail_import import parse_formular, parse_mailtext, parse_reservationsmail

FORMULAR_EN = """Mia
Beispiel
12 Maple Road
K1A0B1
Lakeview
Canada
6135550147
mia.beispiel@example.com
Objekt: Wohnwagen / Caravan (max. 6.5 m)
Ausstattung: mit Strom / with electricity
Länge des Camper/Wohnwagen: 4.5 – 5.5 m
Number of adults
(ab 16 Jahre): 3
Number of children
(5 bis 15 Jahre): 0
Number of infants
(bis 5 Jahre): 0
Gewünschtes Anreisedatum: 2027-07-02
Gewünschtes Abreisedatum: 2027-07-05
Nachricht: Hello, Looking for a campsite. We will rent a camper. Please let me know if you have a spot available.

Thank you,

Mia
"""

FORMULAR_DE = """Peter
Muster
Dorfstrasse 5
3700
Spiez
Schweiz
+41 79 555 01 23
peter.muster@example.ch
Objekt: Zelt / Tent
Ausstattung: ohne Strom / without electricity
Number of adults
(ab 16 Jahre): 2
Number of children
(5 bis 15 Jahre): 1
Number of infants
(bis 5 Jahre): 1
Gewünschtes Anreisedatum: 14.08.2027
Gewünschtes Abreisedatum: 17.08.2027
Nachricht: Guten Tag, wir möchten gerne mit unseren Kindern zelten. Freundliche Grüsse
"""


def _mail(text, html=False):
    msg = EmailMessage()
    msg["From"] = "Webseite <formular@example.ch>"
    msg["To"] = "info@camping-aeschi.ch"
    msg["Subject"] = "Neue Reservationsanfrage"
    msg["Date"] = "Wed, 28 Oct 2026 12:00:00 +0100"
    if html:
        msg.set_content(text)
        msg.add_alternative("<html><body><p>" + text.replace("\n", "<br>\n") + "</p></body></html>", subtype="html")
    else:
        msg.set_content(text)
    return msg


def test_formular_englisch_alle_felder():
    p = parse_reservationsmail(_mail(FORMULAR_EN))
    assert p.gast_name == "Mia Beispiel"
    assert p.gast_email == "mia.beispiel@example.com"  # nicht die Absenderadresse des Formulars
    assert p.gast_telefon == "6135550147"
    assert (p.gewuenscht_von, p.gewuenscht_bis) == (date(2027, 7, 2), date(2027, 7, 5))
    assert p.stellplatz_typ == "wohnwagen"
    assert (p.anzahl_erwachsene, p.anzahl_kinder) == (3, 0)
    assert p.sprache == "en"
    assert "Ausstattung: mit Strom / with electricity" in p.bemerkung
    assert "Länge Camper/Wohnwagen: 4.5 – 5.5 m" in p.bemerkung
    assert "Adresse: 12 Maple Road, K1A0B1 Lakeview, Canada" in p.bemerkung
    assert p.bemerkung.endswith("Mia")  # Nachricht vollständig
    assert "Kleinkinder" not in p.bemerkung


def test_formular_deutsch_punktdatum_kleinkinder_zelt():
    p = parse_reservationsmail(_mail(FORMULAR_DE))
    assert p.gast_name == "Peter Muster"
    assert p.gast_telefon == "+41 79 555 01 23"
    assert (p.gewuenscht_von, p.gewuenscht_bis) == (date(2027, 8, 14), date(2027, 8, 17))
    assert p.stellplatz_typ == "zeltwiese"
    assert (p.anzahl_erwachsene, p.anzahl_kinder) == (2, 1)
    assert "Kleinkinder (bis 5 Jahre): 1" in p.bemerkung
    assert p.sprache == "de"


def test_formular_als_html_mail():
    p = parse_reservationsmail(_mail(FORMULAR_EN, html=True))
    assert (p.gast_name, p.anzahl_erwachsene, p.stellplatz_typ) == ("Mia Beispiel", 3, "wohnwagen")


def test_laenge_mit_camper_im_feldnamen_aendert_den_typ_nicht():
    # "Länge des Camper/Wohnwagen" enthält "Camper" – massgebend ist nur das Feld "Objekt"
    assert parse_formular(FORMULAR_EN)["stellplatz_typ"] == "wohnwagen"


def test_freitextmail_bleibt_bei_bisheriger_erkennung():
    assert parse_formular("Guten Tag, wir kommen vom 3.7. bis 6.7. mit 2 Erwachsenen.") is None


def test_eingefuegter_text_ergibt_vollstaendige_anfrage(client):
    r = client.post("/reservationsanfragen/mail-import/text", json={"text": FORMULAR_EN})
    assert r.status_code == 201, r.text
    a = r.json()
    assert a["vollstaendig"] is True and a["status"] == "geprueft_vollstaendig"
    assert a["quelle"] == "email" and a["gast_telefon"] == "6135550147"
    assert "Nachricht des Gastes" in a["bemerkung"]
    assert a["rohtext"].count("Gewünschtes Anreisedatum") == 1

    # nochmals einfügen -> wird erkannt
    assert client.post("/reservationsanfragen/mail-import/text", json={"text": FORMULAR_EN}).status_code == 409
    # Text ohne E-Mail-Adresse
    assert client.post("/reservationsanfragen/mail-import/text", json={"text": "Bitte rufen Sie mich zurück."}).status_code == 422


def test_eingefuegter_freitext_mit_adresse():
    p = parse_mailtext("Hallo, wir möchten vom 10.7.2027 bis 12.7.2027 mit 2 Erwachsenen zelten. a.b@example.ch",
                       jetzt=datetime(2026, 10, 28, tzinfo=timezone.utc))
    assert p.gast_email == "a.b@example.ch" and p.anzahl_erwachsene == 2 and p.stellplatz_typ == "zeltwiese"
