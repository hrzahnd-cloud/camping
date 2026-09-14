# Campingverwaltung Aeschi – Backend

Python (FastAPI) + PostgreSQL-Backend, aufgebaut nach dem gemeinsam
erarbeiteten Konzeptdokument (`campingverwaltung-konzept.md`). Dieses
README ist der Einstiegspunkt für alle, die als Nächstes an diesem
Code weiterarbeiten – Entwickler:innen ebenso wie die für Hosting,
Zugriffssteuerung und 2FA zuständigen Fachpersonen.

## ⚠️ Wichtiger Hinweis zum aktuellen Stand

Dieser Code wurde in einer **netzwerkisolierten Sandbox** erstellt
(kein Internetzugriff möglich). Das bedeutet:

- **Nicht getestet werden konnten:** alles, was FastAPI, SQLAlchemy,
  Pydantic oder eine echte PostgreSQL-Verbindung braucht (also der
  grösste Teil der Anwendung) – diese Pakete liessen sich in der
  Sandbox nicht installieren.
- **Echt getestet wurden:** die PDF-Rechnungserzeugung (`reportlab`
  war verfügbar) und die HESTA-Aggregationslogik (reine Python-Logik,
  ohne Abhängigkeiten) – dabei wurde sogar ein Bug bei
  monatsübergreifenden Aufenthalten gefunden und behoben.
- Der gesamte Code wurde sorgfältig manuell auf Konsistenz geprüft
  (Syntax, Beziehungen zwischen Modellen, Importe), das ersetzt aber
  keinen echten Lauf gegen eine Datenbank.

**Erster Schritt für euer Team:** die Schritte unter [Setup](#setup)
durchgehen und den Smoke-Test ausführen (`pytest tests/ -v`), bevor
mit der fachlichen Weiterentwicklung begonnen wird.

## Was ist fertig?

| Bereich | Status |
|---|---|
| Datenmodell (alle Entitäten aus dem Konzept) | ✅ vollständig |
| Reservationsanfragen: Anlegen, Vollständigkeitsprüfung | ✅ Basis vorhanden |
| Gäste, Buchungen, Aufenthalte, Check-in/-out | ✅ Basis vorhanden |
| Artikel/Saison/MWST: Preisfindung | ✅ funktionsfähig |
| Rechnungserstellung: Nummernvergabe, MWST-Berechnung, PDF | ✅ funktionsfähig (Datenmodell-Ebene) |
| Auswertungen (Umsatz nach Kunde/Monat/Artikel, Zahlungsmethoden) | ✅ Basis vorhanden (nur JSON, kein Excel/PDF-Export) |
| Grunddaten (Preise camping-aeschi.ch, MWST-Sätze, Saisons 2026) | ✅ `app/seed.py` |
| E-Mail-Versand (Reservationsantwort, Rechnung) | ⏳ Modell vorhanden, SMTP-Versand noch zu implementieren |
| Feratel-Schnittstelle (SOAP/XML) | ❌ bewusst nicht implementiert – siehe unten |
| HESTA-Live-Übermittlung | ⏳ Aggregationslogik fertig, PDF-Befüllung/Upload noch offen |
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

# 6. Datenbankschema erzeugen (erste Migration)
alembic revision --autogenerate -m "initiales Schema"
alembic upgrade head

# 7. Grunddaten einspielen (Preise, MWST-Sätze, Saisons)
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
alembic/        Datenbank-Migrationen
tests/          Smoke-Test
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

## Empfohlene nächste Schritte

1. Team richtet lokale Umgebung ein, führt Setup + Smoke-Test aus,
   meldet zurück, ob alles wie erwartet läuft
2. Erste echte Migration gegen eine echte PostgreSQL-Instanz durchführen
3. Entscheidung zu Authentifizierung/Login treffen (fehlt noch komplett)
4. Restliche Router ergänzen (Newsletter, EmailVersand tatsächlicher
   SMTP-Versand, Feratel/HESTA-Endpunkte)
5. Frontend aufsetzen (in diesem Repo nicht enthalten)
