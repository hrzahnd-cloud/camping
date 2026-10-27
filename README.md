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
| Einstellungen | Module ein-/ausschalten |

Die Zuteilung einzelner Stellplätze erfolgt ausserhalb des Tools; die Belegung zeigt deshalb
Reservationen je Stellplatz-Typ. Eine akzeptierte Reservation bleibt eine Reservation mit
Status «akzeptiert» (es entsteht keine Buchung mit Stellplatz).

**Module:** Buchungen, Artikel & Preise, Rechnungen, Auswertungen, HESTA und Feratel sind im
Backend vollständig vorhanden und in der Datenbank vorgesehen, aber standardmässig
ausgeschaltet. Unter *Einstellungen* lassen sie sich ohne Deployment einschalten; ihre eigene
Oberfläche folgt in einer späteren Phase (bis dahin Verweis auf die API).

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
