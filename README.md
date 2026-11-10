# Campingverwaltung Aeschi

Python (FastAPI) + PostgreSQL-Backend mit Bedienoberfläche (React), aufgebaut nach dem gemeinsam
erarbeiteten Konzeptdokument (`campingverwaltung-konzept.md`). Dieses
README ist der Einstiegspunkt für alle, die als Nächstes an diesem
Code weiterarbeiten – Entwickler:innen ebenso wie die für Hosting,
Zugriffssteuerung und 2FA zuständigen Fachpersonen.

## Aktueller Stand (Oktober 2026)

- Läuft auf Atoll (Testumgebung `camping-test.eutima.ch`), PostgreSQL-Datenbank angebunden.
- Automatisch getestet: `pytest` (Backend, SQLite) und ein CI-Workflow auf GitHub, der das
  Docker-Image ohne Cache baut und Oberfläche, Zertifikate, Node.js und Tests im Image prüft.
- **Noch ohne Login:** Zugangsschutz, 2FA sowie Mailkonto (IMAP/SMTP) richtet Eutima ein.
  Bis dahin keine echten Gästedaten erfassen.

## Bedienoberfläche

Die Oberfläche liegt unter `/` (Seiten als `/#/reservationen`, `/#/belegung`, …), die API
wie bisher daneben (`/docs`). Phase 1 umfasst:

| Bereich | Inhalt |
|---|---|
| Reservationen | Posteingang nach Ablagen (zu bearbeiten, warten auf Gast, akzeptiert, abgelehnt/storniert), Anfrage erfassen und ergänzen, Status setzen, Originalnachricht |
| Belegung | Monat / Woche / freier Zeitraum; Zeitband oder Liste je Stellplatz-Typ (Zelt, Wohnwagen, Camper, Zwärgli, Spycher) mit Erwachsenen (E) und Kindern (K) |
| Gäste | Suchen, erfassen, bearbeiten |
| Einstellungen | Antwortvorlagen (DE/FR/IT/EN) mit Vorschau, Betriebsangaben (Signatur, Infoblock, IBAN/BIC, TWINT), MWST-Sätze je Gültigkeit, Postfach (Abrufstand, nicht zugeordnete Mails), Module ein-/ausschalten |

**Mails aus dem Mailkonto des Campings:** Reservationsmails und Antworten werden per «Umleiten»
(empfohlen) oder «Weiterleiten» in ein eigenes Tool-Postfach geschickt, das die App per IMAP
abruft (`IMAP_*`). Weitergeleitete Mails werden ausgepackt (Gmail, Outlook, Apple Mail,
Thunderbird, auch als Anhang). Mails von eigenen Adressen (`MAIL_EIGENE_ADRESSEN`, z.B. per BCC)
gelten als Antwort und werden der Anfrage zugeordnet; Antworten von Gästen («Re:/AW:» oder
Mail-Verweise) ebenfalls und erscheinen als «Neue Mail». Details: `app/services/mailverlauf.py`.

**Antwortmails:** Zwei Antwortarten, je mit Vorlage in vier Sprachen (Einstellungen ›
Antwortvorlagen):

- «Antwort mit Anzahlung» (nur bei vollständiger Reservation): Text mit Infoblock und
  Zahlungsangaben. Die Anzahlung wird von Hand eingegeben, eine Zahlungsfrist ist optional.
  Status danach «Antwort gesendet».
- «Freie Antwort» (immer möglich, auch bei fehlenden Angaben): nur Anrede, eigener Text und
  Signatur, Betreff «Re: …» auf die letzte Mail des Gastes. Für Rückfragen wie «Sind Hunde
  erlaubt?». Status danach «In Abklärung» (Ablage «Warten auf Gast»); ein späterer Status wie
  «Antwort gesendet» wird nicht zurückgesetzt.

- «Bestätigung definitiv» (nach dem Akzeptieren): Reservation ist definitiv gebucht, mit Dank
  für die gutgeschriebene Anzahlung bzw. ohne diesen Satz, wenn ohne Anzahlung akzeptiert wurde.

**Anfragenummer:** Jede Anfrage erhält beim Anlegen eine Nummer «Jahr-Nummer» (2026-001, …,
Migration 0006 nummeriert bestehende Anfragen nach). Sie steht im Betreff jeder Antwort
(«… [Anfrage 2026-042]») und als Zahlungszweck in der Antwort mit Anzahlung. Beim Mail-Import
hat sie Vorrang vor allen anderen Merkmalen der Zuordnung, weil sie auch Weiterleitungen und
Antworten von anderen Adressen übersteht. In der Liste lässt sich nach ihr suchen.

**Akzeptieren:** «Zahlung erhalten, akzeptieren» fragt den tatsächlich gutgeschriebenen Betrag
in CHF ab (z.B. nach Umrechnung einer Zahlung in Euro), dazu Zahlungsart und Datum. Er wird als
Zahlung zur Anfrage gespeichert und ist die Grundlage für die spätere Rechnung; die verlangte
Anzahlung bleibt zum Vergleich erhalten. Ohne Betrag wird ohne Anzahlung akzeptiert (z.B.
Stammgäste). Danach wird die Bestätigung vorbereitet.

Der Text lässt sich anpassen, kopieren bzw. im Mailprogramm öffnen; «Als gesendet markieren»
speichert ihn im Mailverlauf und setzt den Status. Eigene Antworten, die per BCC/Weiterleitung
ins Tool-Postfach kommen, gelten als «Antwort mit Anzahlung», wenn sie IBAN oder Anzahlung
erwähnen, sonst als freie Antwort. Sobald SMTP eingerichtet ist, kann die App selbst versenden.
Signatur, IBAN usw. liegen in der Datenbank, nicht im (öffentlichen) Code.

**Belegung:** Die Zuteilung einzelner Stellplätze erfolgt ausserhalb des Tools; die Belegung
zeigt deshalb Reservationen und Aufenthalte je Stellplatz-Typ. Gezählt werden nur akzeptierte
Reservationen und Aufenthalte. Zelt, Wohnwagen und Camper zählen gegen die Platzzahl (Standard
50, Meldung ab 45 belegten Plätzen pro Nacht, beides unter Einstellungen › Belegung), Zwärgli und
Spycher separat. Die Übersicht zeigt je Nacht die Auslastung, die Zahlen je Typ sowie Anreisen
und Abreisen; ein Klick öffnet rechts den Tag bzw. den Eintrag, ohne die Seite zu verlassen.

**Check-in, Aufenthalt:** Ab dem Anreisetag lässt sich eine akzeptierte Reservation in der
Belegung einchecken: Gast, Buchung und Aufenthalt entstehen in
einem Schritt. Pflicht sind Name und Nationalität (HESTA), Adresse und Platznummer sind optional;
die Reservation wird «angereist». Gäste ohne
Reservation (Nebensaison) über «Check-in ohne Reservation». «Abreise erfassen» gibt den Platz
frei. Ist ein Gast nicht erschienen, zeigt «Heute» ihn am Morgen danach; «Nicht angereist» gibt
den Platz frei, eine Anzahlung bleibt erfasst. Stornieren behält die Anfrage, «Endgültig
löschen» entfernt sie mit Mailverlauf und Zahlungen (z.B. Testdaten).

**Personen:** Erwachsene ab 16 Jahren, Kinder 6–15 (ohne Kurtaxe), Kleinkinder 0–5 (gratis).
Kleinkinder werden separat gespeichert; in der Belegung und in Mails zählen sie bei den Kindern
mit. Sind mehr Plätze belegt als vorhanden, zeigt die Belegung «überbucht».

**Aufenthalte (Modul «Buchungen & Aufenthalte», einschaltbar):** Register «Auf dem Platz»,
«Anreisen» (nächste 7 Tage und noch nicht Angereiste) und «Abgereist» (letzte 60 Tage). Die
Suche über den Registern findet Name, Platz, Reservationsnummer und Land (Code oder Name) –
bei «Abgereist» auch ältere Abreisen; die Zahlen an den Registern zeigen die Treffer. Je Aufenthalt:
Gast bearbeiten (Nationalität Pflicht), ganzen Aufenthalt verlängern/verkürzen und die
*Leistungen* – jede Zeile mit Art, Anzahl und eigenem Zeitraum (Personen, Stellplatz, Zwärgli,
Spycher, Strom, Auto, Motorrad, Umweltabgabe, Wassertank). So lassen sich Abwesenheiten
(«2 von 4 Kindern zwei Nächte weg» teilt die Zeile auf) und Personen abbilden, die mit eigenem
Zelt nur einen Teil des Aufenthalts dabei sind – abgerechnet über den ursprünglichen
Aufenthalt; ein solches Zusatzzelt zählt nicht als eigener Stellplatz. Die Umweltabgabe kommt
beim Check-in automatisch dazu: pro Stellplatz (Zelt, Wohnwagen, Camper) und Nacht.
Fahrzeuge: Der Check-in schlägt bei Zelt und Wohnwagen 1 Auto vor (bei Camper, Zwärgli, Spycher
keines); Autos und Motorräder sind anpassbar, Fahrräder werden nicht erfasst. Taxen je Personennacht:
Beherbergungsabgabe für alle Erwachsenen, Kurtaxe nur für kurtaxepflichtige. Ohne das Modul
bleibt der kurze Check-in samt Abreise in der Belegung wie bisher. Preise folgen mit «Artikel &
Preise».

**Artikel & Preise (Modul, einschaltbar; Pflege unter Einstellungen › Artikel & Preise, nicht im Hauptmenü):** Saisons je Jahr – Vorsaison 1.5.–30.6.,
Hauptsaison 1.7.–31.8., Nachsaison 1.9.–30.9.; Oktober bis April geschlossen (saisonale Artikel
ohne Preis). Saisondaten und Preise je Saison zentral auf einer Seite änderbar, ganzjährige
Preise (Strom, Umweltabgabe, Wassertank, Zwärgli, Spycher, Kleinkinder) gelten für alle Jahre.
«Jahr aus Vorjahr übernehmen» kopiert Saisons und Preise. Im Aufenthalt erscheinen dann die
Beträge je Leistung (je Nacht mit dem Preis der Saison), Taxen und Total inkl. MWST.
Wassertank ab 2 Nächten inbegriffen; Zwärgli/Spycher mit 2 Personen je Nacht inbegriffen,
weitere Personen zum Personenpreis.

**Unverbindlicher Preis in der Bestätigung:** Platzhalter `{{preisProNacht}}` (in den
Startvorlagen enthalten; unveränderte frühere Vorlagen werden ergänzt). Preis pro Nacht aus
Erwachsenen, Kindern (Kleinkinder gratis), Stellplatz, Umweltabgabe sowie Kurtaxe und
Beherbergungsabgabe; Zwärgli/Spycher für 2 Personen plus weitere Personen und Taxen. Je Saison
eine Zeile, ohne MWST-Angabe und ohne Fahrzeuge. Nur mit Modul «Artikel & Preise»; ausserhalb
der Saison bleibt die Zeile leer (mit Hinweis beim Vorbereiten).

**Rechnungen (Modul, einschaltbar):** Register «Offen», «Bezahlt», «Storniert», «Alle»; die Suche
findet Rechnungsnummer, Gast, Reservationsnummer und Betrag («204» oder «204,50»). Entstehen im Aufenthalt bei der Abreise («Rechnung
erstellen»): je Leistung, Saison und Preis eine Zeile, Zwärgli/Spycher mit inbegriffenen
Personen, Kurtaxe und Beherbergungsabgabe (ohne MWST), die Anzahlung als eigene Zeile abgezogen.
Bar oder TWINT gilt sofort als bezahlt, «offen» für eine spätere Überweisung; Kartenzahlung unter
Einstellungen › Zahlungsarten einschaltbar. Nummer «JJJJ-1000» fortlaufend je Jahr. Solange eine
gültige Rechnung besteht, ist der Aufenthalt gesperrt; Storno behält die Nummer und gibt den
Aufenthalt frei. Das PDF wird bei Bedarf aus der gespeicherten Rechnung erzeugt (Absender und
MWST-Nummer unter Betriebsangaben). Seite «Rechnungen»: offen / bezahlt / storniert, Zahlung
erfassen, PDF, Storno.

**Auswertungen (Modul, einschaltbar):** Jahr wählen, Vergleich mit einem Vorjahr (Daten aus dem Tool).
*Einnahmen & MWST* pro Monat nach Zahlungseingang (vereinnahmtes Entgelt): Anzahlungen und
Schlusszahlungen, je Zahlung im Verhältnis des Rechnungstotals aufgeteilt in MWST-pflichtigen
Umsatz je Satz und durchlaufende Taxen; Anzahlungen ohne Rechnung vorläufig als Beherbergung.
*Übernachtungen & Taxen* pro Monat nach Nacht (Kontrolle zu Feratel): Ankünfte, Personennächte
Erwachsene/Kinder/Kleinkinder, Kurtaxe nur Pflichtige, Beherbergungsabgabe, Nächte je Stellplatz.
*Saison (Buchhaltung)*: Rechnungen des Jahres, MWST auf den Rechnungstotalen, Taxen, Umsatz je
Leistung, Einnahmen je Zahlungsart, Offenes – als Excel und PDF. Rechnungen mit Logo (Upload unter
Betriebsangaben, gespeichert in der Datenbank); MWST je Satz einmal auf dem Total.

**Absage «ausgebucht»:** Sind im gewünschten Zeitraum einer offenen Anfrage Nächte voll belegt
(alle Stellplätze Zelt/Wohnwagen/Camper, ohne diese Anfrage), zeigt die Reservation den Hinweis und
den Knopf «Absage: ausgebucht» – auch wenn nur ein Teil der Nächte voll ist. Die Vorlage (4 Sprachen)
setzt mit `{{ausgebuchtZeitraum}}` die vollen Nächte ein und mit `{{wiederFrei}}` den nächsten freien
Zeitraum gleicher Länge innerhalb der Saisons (bis 90 Tage voraus). Nach dem Versand: «abgelehnt».

**Gästekarte (Modul, bisher «Feratel», einschaltbar):** Menüpunkt mit dem Zugang zum feratel Web Client
von Thun-Thunersee Tourismus (webclient4.deskline.net/GRI/de/Login), in dem die Betreiberin Meldeschein und
PanoramaCard von Hand erfasst. Der Web Client lässt sich nicht einbetten (frame-ancestors 'none') und öffnet sich
deshalb in einem eigenen Fenster; Zugangsdaten laufen nicht durch das Tool. Bewusst keine Verknüpfung mit
Reservation/Aufenthalt (Wunsch des Betriebs).

**HESTA (Modul, einschaltbar):** Monatsrapport für die Beherbergungsstatistik des BFS: Ankünfte und
Übernachtungen je Nationalität des Hauptgastes (statt Wohnsitzland), für alle Personen inkl. Kinder, aus
den Aufenthalten; alphabetisch nach Land. Rapport erstellen und ablegen (Ablage mit PDF), nach der
Erfassung beim BFS «als gemeldet markieren»; bis dahin erinnert «Heute» Anfang Monat an die fällige
Meldung. Mails des BFS (@bfs.admin.ch, monatliche Zugangsdaten) landen beim Postfach-Abruf im Modul HESTA
statt bei den Reservationen; bis das Postfach angebunden ist, lassen sie sich einfügen. Achtung: ohne
Anmeldung sind diese Zugangsdaten für alle sichtbar, die die Adresse kennen.

**Testdaten:** `scripts/testdaten_juli2027.js` erzeugt über die API erfundene Reservationen für
Juli 2027 bis zur Vollbelegung samt Antworten, Zahlungen und Bestätigungen (Adressen
@example.com/.org/.net) und entfernt sie mit `--loeschen` wieder.
`scripts/testdaten_nebensaison.js` erzeugt ab morgen bis Mitte Dezember Nebensaison-Daten mit
bereits eingecheckten Gästen, Anreisen, Wintercampern und offenen Anfragen.

**Module:** Alle Module sind im
Backend vorhanden, aber standardmässig ausgeschaltet. Unter *Einstellungen* lassen sie sich
ohne Deployment einschalten; ihre eigene Oberfläche folgt schrittweise (bis dahin Verweis auf
die API).

Entwicklung der Oberfläche (Node.js ≥ 24.22.1, siehe `frontend/.nvmrc`):

```bash
cd frontend
npm ci
npm run dev      # http://localhost:5173, leitet API-Aufrufe an uvicorn auf :8000 weiter
npm run build    # erzeugt frontend/dist, das FastAPI unter "/" ausliefert
```

Im Docker-Image wird die Oberfläche in einer eigenen Build-Stufe gebaut; Node.js gelangt
nicht ins laufende Image.

## Was ist fertig?

| Bereich | Status |
|---|---|
| Datenmodell (alle Entitäten aus dem Konzept) | ✅ vollständig |
| Reservationsanfragen: Anlegen, Vollständigkeitsprüfung | ✅ Basis vorhanden |
| Reservationsanfragen aus E-Mails (IMAP-Postfach, `.eml`-Import) | ✅ fertig, wartet auf `IMAP_*`-Zugangsdaten (`app/services/mail_import.py`) |
| Gäste, Buchungen, Aufenthalte, Check-in/-out | ✅ Basis vorhanden |
| Artikel/Saison/MWST: Preisfindung | ✅ funktionsfähig |
| Rechnungserstellung: Nummernvergabe, MWST-Berechnung, PDF | ✅ funktionsfähig (Datenmodell-Ebene) |
| Kurtaxe (Aeschi, CHF 3.50) und Beherbergungsabgabe (Kanton Bern, CHF 1.00): je Nacht, nur Personen ab 16 Jahren, automatisch auf der Rechnung (`app/services/taxen.py`, Vorschau: `GET /rechnungen/taxen-vorschau`) | ✅ funktionsfähig |
| Feratel-Gästemeldung: Meldeschein-Vorbereitung für den WebClient, Prüfung der Pflichtangaben, Protokoll der Meldescheinnummer (`/feratel/...`) | ✅ funktionsfähig (manueller Weg) |
| Auswertungen (Umsatz nach Kunde/Monat/Artikel, Zahlungsmethoden) | ✅ Basis vorhanden (nur JSON, kein Excel/PDF-Export) |
| Grunddaten (Preise camping-aeschi.ch, MWST-Sätze, Saisons 2026) | ✅ `app/seed.py` |
| E-Mail-Versand (Reservationsantwort, Rechnung) | ⏳ Modell vorhanden, SMTP-Versand noch zu implementieren |
| Feratel-Schnittstelle (SOAP/XML) | ❌ bewusst nicht implementiert – siehe unten |
| HESTA-Monatsmeldung: Aggregation, PDF, CSV, Meldeprotokoll (`/hesta/...`) | ✅ funktionsfähig |
| HESTA-Versand per E-Mail ans BFS | ⏳ gebaut, aber gesperrt (`HESTA_EMAIL_VERSAND_AKTIV=false`): braucht BUR-Nummer, SMTP und BFS-Bestätigung des Formats |
| Mailchimp-Newsletter-Sync | ❌ bewusst nicht implementiert – siehe unten |
| Kreditkarten-Zahlung | ❌ bewusst nicht implementiert – siehe unten |
| Excel-Export der Auswertungen | ❌ noch zu bauen (`openpyxl`) |
| Authentifizierung/Login, 2FA | ❌ **nicht Teil dieses Codes** – siehe Abschnitt „Infrastruktur" |

## Setup

```bash
# 1. Virtuelle Umgebung anlegen
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 2. Abhängigkeiten installieren
pip install -r requirements.txt

# 3. Umgebungsvariablen konfigurieren
cp .env.example .env
# .env öffnen und DATABASE_URL mit echten Zugangsdaten befüllen

# 4. PostgreSQL-Datenbank bereitstellen (lokal z.B. via Docker)
docker run --name camping-db -e POSTGRES_USER=camping_user \
  -e POSTGRES_PASSWORD=changeme -e POSTGRES_DB=campingverwaltung \
  -p 5432:5432 -d postgres:16

# 5. Smoke-Test ausführen (SQLite, prüft nur die Modellstruktur)
pytest tests/ -v

# 6. Datenbankschema erzeugen bzw. aktualisieren
alembic upgrade head

# 7. Grunddaten einspielen (Preise, MWST-Sätze, Saisons)
#    Im Docker-Container geschieht das beim Start automatisch, aber nur
#    bei leerer Datenbank (python -m app.seed --falls-leer).
python -m app.seed

# 8. Server starten
uvicorn app.main:app --reload
```

Die interaktive API-Dokumentation ist danach unter `http://localhost:8000/docs` erreichbar.

## Projektstruktur

```
app/
  models/       SQLAlchemy-Modelle, 1:1 nach Konzeptdokument-Entitäten
  schemas/      Pydantic-Schemas (Ein-/Ausgabe der API)
  routers/      FastAPI-Endpunkte
  services/     Fachlogik: MWST-Berechnung, Rechnungsnummer, PDF,
                HESTA-Aggregation, Feratel-/Mailchimp-Anbindung (Stubs)
  config.py     Einlesen der Umgebungsvariablen
  database.py   DB-Verbindung/Session
  main.py       FastAPI-App, Router-Einbindung
  seed.py       Grunddaten für einen frischen Betrieb
frontend/       Bedienoberfläche (React + Vite)
alembic/        Datenbank-Migrationen
scripts/        Prüfskripte (CA-Zertifikate, Node.js, TLS)
tests/          pytest
```

## Bewusst nicht implementiert – und warum

Drei Bereiche sind als klar markierte Platzhalter angelegt
(`NotImplementedError` mit erklärendem Text), weil ihnen externe
Voraussetzungen fehlen, die nicht im Code lösbar sind:

1. **`app/services/feratel_client.py`** – die SOAP/XML-Kommunikation
   mit Feratel Deskline 3.0 braucht die technische WSDL-Dokumentation,
   die erst nach der PMS-Partner-Freischaltung durch Thun-Thunersee
   Tourismus verfügbar ist.
2. **`app/services/mailchimp_client.py`** – braucht ein eingerichtetes
   Mailchimp-Konto mit Audience und API-Key.
3. **Kreditkarten-Zahlung** (`Zahlungsanbieterkonfiguration` im
   Datenmodell vorbereitet, aber `aktiv=False`) – braucht einen
   Vertrag mit einem Zahlungsanbieter (Saferpay/Datatrans/Stripe o.ä.).

**HESTA – elektronische Meldung (Stand der Abklärung):** Das BFS bietet
keine offene API. Die „PMS-Schnittstelle" (bfs.admin.ch → Digitale Eingabe der
Anzahl Logiernächte) funktioniert so, dass die Software die Zahlen per E-Mail
an `hotelstatistik@bfs.admin.ch` schickt; vorausgesetzt wird eine BUR-Nummer,
die das BFS auf Anfrage vergibt. Das Dateiformat ist öffentlich nicht
dokumentiert. Bis das BFS Format und Freischaltung bestätigt, gilt der
PDF-Weg (`GET /hesta/pdf`, danach `.../als-eingereicht-markieren`).

Das Datenmodell ist für alle drei Fälle bereits vollständig vorbereitet
– sobald die externen Voraussetzungen stehen, ist „nur" die jeweilige
Service-Datei zu füllen, keine Strukturänderung nötig.

## Infrastruktur (Hosting, Zugriffssteuerung, 2FA)

Wie besprochen liegt das ausserhalb dieses Codes und wird von den
entsprechenden Fachpersonen übernommen. Für sie relevant:

- Die App ist eine zustandslose FastAPI-Anwendung (ASGI), lauffähig
  hinter jedem Standard-Reverse-Proxy (z.B. nginx, Caddy) via
  `uvicorn`/`gunicorn`.
- Sie braucht eine PostgreSQL-Datenbank (Version 14+ empfohlen) sowie
  Schreibzugriff auf ein Verzeichnis für generierte PDFs
  (`generierte_dokumente/`, Pfad aktuell hartkodiert – für Produktion
  auf einen dauerhaften Speicherort/Objektspeicher umstellen).
- Secrets (DB-Passwort, SMTP, Mailchimp, Feratel) werden ausschliesslich
  über Umgebungsvariablen erwartet (siehe `.env.example`), nie im Code.
- **Authentifizierung/Login/2FA sind bewusst nicht enthalten** – hier
  fehlt noch eine Entscheidung, ob z.B. FastAPI-Users, ein
  vorgelagerter Identity-Provider (Keycloak, Auth0 o.ä.) oder eine
  andere Lösung zum Einsatz kommt. CORS ist aktuell offen (`*`) und
  MUSS vor Produktivbetrieb auf die echte Frontend-Domain eingeschränkt
  werden (`app/main.py`).
- **CA-Zertifikate im Docker-Image:** stammen aus dem Debian-Paket
  `ca-certificates` (System) und aus `certifi` (httpx). Der Build prüft
  beide Vertrauensspeicher mit `scripts/check_ca_bundle.py` und bricht bei
  unsicheren oder vom eMudhra-Vorfall (Oktober 2026) betroffenen
  Zertifikaten ab. Nach Sicherheitsmeldungen zu CA-Zertifikaten das Image
  ohne Cache neu bauen:
  `docker build --pull --no-cache -t campingverwaltung .`
  Details: `docs/sicherheit-ca-zertifikate.md`.
- **Node.js:** Das Image enthält kein Node.js. Der Build bricht ab, falls
  eine verwundbare Node-Laufzeit hineingerät (Node2Shell, CVE-2026-111497;
  `scripts/check_node_versions.py`). Details: `docs/sicherheit-node2shell.md`.

## Empfohlene nächste Schritte

1. Team richtet lokale Umgebung ein, führt Setup + Smoke-Test aus,
   meldet zurück, ob alles wie erwartet läuft
2. Erste echte Migration gegen eine echte PostgreSQL-Instanz durchführen
3. Entscheidung zu Authentifizierung/Login treffen (fehlt noch komplett)
4. Restliche Router ergänzen (Newsletter, EmailVersand tatsächlicher
   SMTP-Versand, Feratel/HESTA-Endpunkte)
5. Frontend aufsetzen (in diesem Repo nicht enthalten)
