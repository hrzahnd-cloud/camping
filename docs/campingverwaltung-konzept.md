# Campingverwaltungssoftware – Konzept & Datenmodell

## 1. Ausgangslage

Web-App zur Verwaltung eines Campingplatzes (Kanton Bern, Region Thunersee, Gemeinde Aeschi) mit automatischer Meldung der Übernachtungen an das **feratel Deskline WebClient / Deskline 3.0**-System via XML/SOAP-Schnittstelle, als Grundlage für:

- **Kantonale Beherbergungsabgabe** (Kanton Bern) – CHF 1.00 pro Nacht und Gast, Marketingbeitrag
- **Kurtaxe** der Gemeinde/Destination Aeschi – Ansatz konfigurierbar (aktuell in der Praxis rund CHF 3.50/Nacht für Erwachsene, reduzierte Sätze für Kinder), abgeführt über die Tourismusorganisation

Beide Abgaben werden auf Basis der im WebClient bzw. per Schnittstelle gemeldeten Gästedaten berechnet, daher ist eine korrekte, vollständige Gästeerfassung im Kernmodell zentral.

## 2. Architektur (Grobkonzept)

```
┌─────────────────────────┐
│   Web-Frontend (SPA)    │  Rezeption / Verwaltung / Gast-Self-Checkin
└────────────┬─────────────┘
             │ REST/HTTPS
┌────────────┴─────────────┐
│   Backend-API             │  Buchungen, Gäste, Stellplätze, Abrechnung
│  (Business-Logik, Auth)   │
└────┬──────────────┬───────┘
     │              │
┌────┴─────┐   ┌────┴────────────────┐
│ Datenbank │   │ Feratel-Integrations-│
│ (relational)│  │ modul (SOAP/XML)    │
└──────────┘   └────┬─────────────────┘
                     │ HTTPS / SOAP 1.1/1.2
              ┌──────┴────────────┐
              │ Feratel Deskline 3.0│
              │ VT PMS Web Services │
              └─────────────────────┘
```

Das Feratel-Modul läuft als eigener Service/Job:
- sendet bei Check-in/Check-out (oder gebündelt, z. B. stündlich/täglich) Meldedaten
- empfängt Bestätigungen bzw. Fehlercodes
- führt ein Übertragungsprotokoll (Audit-Log) für die Abrechnungssicherheit

## 3. Datenmodell

### 3.1 Übersicht der Kernentitäten

| Entität | Zweck |
|---|---|
| `Campingplatz` | Stammdaten des Betriebs (Feratel-Firmennummer, Gemeindenummer) |
| `Stellplatz` | Physische/buchbare Einheit (Zelt, Wohnwagen, Zwergli, Spycher …) |
| `Reservationsanfrage` | Eingehende Anfrage (E-Mail/Homepage/manuell), vor Umwandlung in eine `Buchung` |
| `Zahlung` | Zahlungseingang/-versuch zu einer Anfrage oder Rechnung (Banküberweisung, TWINT, Kreditkarte, Bar) |
| `Zahlungsanbieterkonfiguration` | Zugangsdaten/Status externer Zahlungsanbieter (aktuell nur vorbereitet, z. B. für Kreditkarte) |
| `EmailVorlage` | Editierbare Antwortmail-Vorlage je Vorlagentyp und Sprache (DE/FR/IT/EN) |
| `EmailVersand` | Protokoll je versendeter Antwortmail (wer, wann, welche Vorlage) |
| `NewsletterAbo` | Einwilligung/Abmeldung einer E-Mail-Adresse für Newsletter, unabhängig von einzelner Buchung |
| `MailchimpKonfiguration` | Zugangsdaten/Status der Mailchimp-Anbindung (API-Key, Audience/Liste) |
| `NewsletterKampagne` | Einzelner Newsletter-Versand (Inhalt, Sprache, Status) |
| `NewsletterVersand` | Protokoll je Empfänger einer Kampagne (Zustellung, Abmeldung, Fehler) |
| `Buchung` | Bestätigte Reservierung eines Stellplatzes über einen Zeitraum |
| `Gast` | Person (Hauptbucher oder Mitreisender) |
| `Aufenthalt` | Verknüpfung Gast ↔ Buchung mit effektiven An-/Abreisedaten (kann von Buchungszeitraum abweichen) |
| `Taxensatz` | Konfigurierbare Abgabensätze (Kurtaxe/Beherbergungsabgabe) nach Gültigkeitszeitraum & Altersgruppe |
| `Mwstsatz` | Zentral verwalteter MWST-Satz (z. B. Sondersatz Beherbergung), historisiert nach Gültigkeitsdatum |
| `Saison` | Zeitraum mit eigener Preisgültigkeit (Hauptsaison, Vor-/Nachsaison) |
| `Artikel` | Verkaufs-/Leistungsposition des Campingplatzes (Person, Stellplatztyp, Zusatzleistung), verweist auf `Mwstsatz` |
| `ArtikelPreis` | Preis eines Artikels für eine bestimmte Saison |
| `Rechnung` / `Rechnungsposition` | Abrechnung Übernachtung, Nebenkosten, Taxen – Position referenziert `Artikel` |
| `Rechnungsnummernzaehler` | Zähler je Jahr für lückenlose, revisionssichere Rechnungsnummern (Format `JJJJ-XXXX`, Start 1000) |
| `FeratelMeldung` | Protokoll jeder Übertragung an die Schnittstelle (Status, Zeitstempel, Fehlercode) |
| `FeratelKonfiguration` | Zugangsdaten & Mapping-Werte für die SOAP-Schnittstelle |

### 3.2 Felder je Entität

**Campingplatz**
- `id`, `name`, `adresse`, `gemeindeNummer` (ÖSTAT-analoger Code), `firmenNummer` (Feratel Mapping-Code), `kanton`

**Stellplatz**
- `id`, `bezeichnung`, `typ` (Zeltwiese, Wohnwagen, Zwergli, Spycher …), `maxPersonen`, `stromAnschluss` (bool), `artikelId` (Verweis auf den zugehörigen Standard-Artikel für die Preisfindung)

**Reservationsanfrage** *(neu)*
- `id`, `quelle` (E-Mail / Homepage-Formular / manuell/Telefon), `eingangsDatum`, `sprache` (erkannt oder gewählt), `gastName`, `gastEmail`, `gastTelefon`, `gewuenschtVon`, `gewuenschtBis`, `stellplatzTyp`, `anzahlErwachsene`, `anzahlKinder`, `bemerkung`, `rohtext` (Original-Mailinhalt zur Nachvollziehbarkeit), `vollstaendig` (bool), `fehlendeAngaben` (Liste, falls unvollständig), `status` (neu / unvollständig / geprüft-vollständig / erstantwort-gesendet / zahlung-ausstehend / bezahlt-akzeptiert / abgelehnt / storniert), `verknuepfteBuchungId` (gesetzt, sobald akzeptiert), `newsletterEinwilligung` (bool, **separate Opt-in-Angabe**, siehe Abschnitt 12)

**Zahlung** *(neu)*
- `id`, `bezugTyp` (`reservationsanfrage` / `rechnung`), `bezugId` (verweist je nach Typ auf `Reservationsanfrage.id` oder `Rechnung.id`), `betrag`, `waehrung` (CHF), `zahlungsart` (`banküberweisung` / `twint` / `kreditkarte` / `bar`), `status` (ausstehend/eingegangen/fehlgeschlagen/storniert), `referenz` (QR-Referenznummer bei Banküberweisung, TWINT-Beleg/Transaktions-ID, Kreditkarten-Transaktions-ID sobald aktiv, bei Bar ggf. Quittungsnummer), `eingegangenAm`, `abgeglichenVon` (Person bei manuellem Abgleich, oder „System" bei künftiger automatischer Bestätigung)
- Hinweis: **Bar** ist naturgemäss nur bei der Vor-Ort-Zahlung einer `Rechnung` (Check-out) relevant, nicht bei der Anzahlung einer `Reservationsanfrage` per Fernzugriff

**Zahlungsanbieterkonfiguration** *(neu, aktuell nur vorbereitet)*
- `id`, `zahlungsart` (`kreditkarte`), `anbieter` (z. B. Saferpay/Datatrans/Stripe – noch offen), `aktiv` (bool, **aktuell `false`**), `zugangsdaten` (verschlüsselt, erst bei Aktivierung befüllt), `webhookUrl` (für automatische Zahlungsbestätigung, sobald angebunden)
- Diese Entität existiert von Anfang an im Modell, bleibt aber bis zur Aktivierung leer/inaktiv – dadurch lässt sich die Kreditkarten-Integration später ohne Datenmodell-Änderung nachrüsten

**EmailVorlage** *(neu)*
- `id`, `typ` (z. B. „Erstantwort mit Zahlungsinformationen", „Rechnung", später erweiterbar um „Zahlungserinnerung", „Absage" …), `sprache` (DE/FR/IT/EN), `betreff`, `koerper` (Text mit Platzhaltern wie `{{gastName}}`, `{{zeitraum}}`, `{{stellplatzTyp}}`, `{{betrag}}`, `{{iban}}`, `{{zahlungsfrist}}`, `{{rechnungsnummer}}`), `aktiv` (bool), `zuletztGeaendertAm`, `zuletztGeaendertVon`

**EmailVersand** *(neu, generalisiert für mehrere Belegtypen)*
- `id`, `bezugTyp` (`reservationsanfrage` / `rechnung`), `bezugId`, `vorlageId`, `gesendetAm`, `gesendetVon` (Benutzer/Person, die den Versand ausgelöst hat), `empfaenger`, `betreffFinal`, `koerperFinal` (fertig befüllte Kopie, für Nachvollziehbarkeit archiviert), `anhangPfad` (bei Rechnungsversand: Pfad zum PDF), `status` (gesendet/fehler)

**NewsletterAbo** *(neu)*
- `id`, `email`, `vorname` (optional), `sprache` (DE/FR/IT/EN – als Mailchimp-Tag/Merge-Feld übertragen), `status` (angemeldet/abgemeldet), `einwilligungAm`, `einwilligungQuelle` (Reservationsanfrage-Checkbox / Check-in-Formular / manuell erfasst), `abgemeldetAm`, `mailchimpMemberId` (nach erfolgreicher Synchronisation), `mailchimpSyncStatus` (offen/synchronisiert/fehler)

**MailchimpKonfiguration** *(neu)*
- `id`, `apiKey` (verschlüsselt), `serverPrefix` (z. B. `us21`, Teil des Mailchimp-API-Endpunkts), `audienceId` (Ziel-Liste/Audience in Mailchimp), `aktiv` (bool), `webhookUrl` (für Rückmeldungen von Mailchimp, z. B. Abmeldungen)

**NewsletterKampagne** *(neu)*
- `id`, `titel` (intern), `sprache`, `betreff`, `inhalt`, `status` (entwurf/geplant/versendet), `geplantAm`, `versendetAm`, `erstelltVon`, `mailchimpCampaignId` (Referenz auf die in Mailchimp erstellte/versendete Kampagne)

**NewsletterVersand** *(neu, optionaler lokaler Spiegel — Mailchimp führt die primäre Versand-/Öffnungsstatistik)*
- `id`, `kampagneId`, `newsletterAboId`, `gesendetAm`, `status` (zugestellt/fehler/abgeprallt), `abmeldelinkVerwendetAm`

**Buchung**
- `id`, `stellplatzId`, `von`, `bis`, `status` (angefragt/bestätigt/eingecheckt/ausgecheckt/storniert), `hauptgastId`, `erstelltAm`, `reservationsanfrageId` (Herkunft, falls aus einer Anfrage entstanden)

**Gast**
- `id`, `vorname`, `nachname`, `geburtsdatum`, `nationalität`, `plz`, `ort`, `land`, `ausweisNummer` (optional), `gastCode` (falls Gemeinde spezifische Gästekategorien verlangt, z. B. Kind/Erwachsen/Ermässigt)

**Aufenthalt**
- `id`, `buchungId`, `gastId`, `ankunft`, `abreise`, `anzahlNaechte` (berechnet), `taxpflichtig` (bool – z. B. bei steuerrechtlichem Wohnsitz in der Gemeinde befreit)

**Taxensatz**
- `id`, `typ` (Kurtaxe / kantonale Beherbergungsabgabe), `gueltigAb`, `gueltigBis`, `altersgruppeVon`, `altersgruppeBis`, `betragProNacht`, `gemeinde`/`kanton`

**Mwstsatz** *(neu, zentrale MWST-Verwaltung)*
- `id`, `code` (z. B. `BEHERBERGUNG`, `NORMAL`, `REDUZIERT`, `AUSGENOMMEN`), `bezeichnung`, `satzProzent`, `gueltigAb`, `gueltigBis` (offen = aktuell gültig)
- Historisiert: bei einer Satzänderung wird ein neuer Datensatz mit neuem `gueltigAb` angelegt, der alte erhält ein `gueltigBis` — bestehende Rechnungen bleiben dadurch unverändert korrekt, da sie den Satz zum Zeitpunkt der Leistung referenzieren (siehe unten)

**Saison** *(neu)*
- `id`, `bezeichnung` (z. B. „Hauptsaison 2026", „Vor-/Nachsaison 2026"), `gueltigAb`, `gueltigBis`

**Artikel** *(neu, zentraler Artikelstamm)*
- `id`, `code`, `bezeichnung`, `kategorie` (Person, Stellplatz/Fahrzeug, Unterkunftseinheit, Zusatzleistung, Taxe), `mwstsatzId` (FK → `Mwstsatz`, aktuell gültiger Satz wird zur Abrechnungszeit aufgelöst), `einheit` (pro Nacht/Person/Tag/Stück)

**ArtikelPreis** *(neu)*
- `id`, `artikelId`, `saisonId`, `preis`

**Rechnung / Rechnungsposition**
- Rechnung: `id`, `buchungId`, `kundeId` (FK → `Gast`, i. d. R. der Hauptgast – denormalisiert für einfache Auswertung „Umsatz nach Kunde"), `nummer` (Format `JJJJ-XXXX`, z. B. `2026-1000` – siehe `Rechnungsnummernzaehler` unten), `datum`, `status` (offen/bezahlt), `gesamtbetrag`, `mwstBetragTotal`, `pdfPfad` (erzeugtes PDF-Dokument), `versendetAm` (falls per E-Mail verschickt)
- Position: `id`, `rechnungId`, `artikelId` (FK → `Artikel`), `menge`, `einzelpreis`, `betrag`, `mwstsatzProzent` (**Snapshot** des zum Leistungsdatum gültigen Satzes – wird bei Rechnungsstellung aus `Artikel.mwstsatzId` aufgelöst und fix in die Position geschrieben, damit spätere Satzänderungen alte Rechnungen nicht verändern), `mwstBetrag` (berechnet)

**Rechnungsnummernzaehler** *(neu)*
- `id`, `jahr`, `letzteVergebeneNummer` (startet bei `999`, sodass die erste Rechnung des Jahres `1000` erhält)
- Beim Erzeugen einer neuen `Rechnung` wird atomar (DB-Transaktion/Sperre) `letzteVergebeneNummer` für das aktuelle `jahr` um 1 erhöht und als `Rechnung.nummer = "{jahr}-{letzteVergebeneNummer}"` übernommen. Existiert für das Jahr noch kein Zähler, wird er mit `999` neu angelegt (nächste Nummer folglich `1000`)
- „Ausgehend von der Saison" bedeutet hier: der Zähler folgt dem Kalenderjahr, in dem die Rechnung gestellt wird (nicht dem Buchungsdatum) – deckt sich in der Praxis mit dem Saisonjahr, da die Camping-Saison innerhalb eines Kalenderjahres liegt
- Wichtig für die Revisionssicherheit: Nummern werden **nie** gelöscht oder wiederverwendet, auch bei stornierten Rechnungen (Storno erhält eine eigene Nummer mit Verweis auf die ursprüngliche Rechnung) – lückenlose Nummerierung ist Voraussetzung für eine ordnungsgemässe Schweizer Buchführung

**FeratelMeldung**
- `id`, `aufenthaltId`, `gesendetAm`, `xmlPayload`, `status` (offen/erfolgreich/fehler), `fehlercode`, `antwortRoh`

**FeratelKonfiguration**
- `landCode` (CH), `gemeindeNummer`, `firmenNummer` (Mapping-Code), `startdatumExport`, `maxAlterKind`, `endpointUrl`, `zugangsdaten` (verschlüsselt gespeichert)

### 3.3 Beziehungen (vereinfacht)

```
Reservationsanfrage n─1 EmailVorlage (via EmailVersand)  Reservationsanfrage 1─n EmailVersand
Reservationsanfrage 1─n Zahlung (bezugTyp = reservationsanfrage)
Rechnung 1─n Zahlung (bezugTyp = rechnung)
Zahlung n─1 Zahlungsanbieterkonfiguration (nur relevant bei zahlungsart = kreditkarte)
Rechnung 1─n EmailVersand (bezugTyp = rechnung)
Rechnung n─1 Gast (kundeId)
Rechnung n─1 Rechnungsnummernzaehler (über Jahr)
Reservationsanfrage 1─1 Buchung (sobald akzeptiert)
Reservationsanfrage 0─1 NewsletterAbo (bei Einwilligung)
NewsletterAbo n─1 MailchimpKonfiguration (Synchronisation)
NewsletterKampagne 1─n NewsletterVersand n─1 NewsletterAbo
Campingplatz 1─n Stellplatz 1─n Buchung 1─n Aufenthalt n─1 Gast
Buchung 1─1 Rechnung 1─n Rechnungsposition n─1 Artikel n─1 Mwstsatz
Artikel 1─n ArtikelPreis n─1 Saison
Aufenthalt 1─n FeratelMeldung
Campingplatz 1─1 FeratelKonfiguration
Taxensatz  (unabhängig, wird zur Berechnungszeit anhand Gültigkeit/Alter zugeordnet)
```

## 4. Kurtaxe/Beherbergungsabgabe – Berechnungslogik

1. Beim Check-out (oder täglich, rollierend) werden alle `Aufenthalte` mit `taxpflichtig = true` ausgewertet.
2. Pro Aufenthalt: `anzahlNaechte × betragProNacht(Taxensatz passend zu Gästealter & Gültigkeitsdatum)`
3. Es entstehen zwei getrennte Rechnungspositionen: **Kurtaxe (Gemeinde)** und **kantonale Beherbergungsabgabe**, da unterschiedliche Empfänger/Verwendungszweck.
4. Ausnahmen (z. B. Personen mit steuerrechtlichem Wohnsitz in der Gemeinde) werden über `taxpflichtig = false` am Aufenthalt abgebildet.

## 5. Feratel-Schnittstelle (SOAP/XML) – Konzept

**Voraussetzung (organisatorisch, vor technischer Umsetzung):**
- Freischaltung als PMS-Partner bei Thun-Thunersee Tourismus / Feratel
- Erhalt von Gemeindenummer, Firmennummer (Mapping-Code) und Zugangsdaten für „Deskline 3.0 VT PMS Web Services“

**Ablauf pro Meldung:**
1. Trigger: Check-in abgeschlossen, Check-out abgeschlossen, oder täglicher Batch-Lauf
2. Backend erstellt XML-Meldeblatt aus `Aufenthalt` + `Gast`-Daten (inkl. Gastcode für Altersgruppe/Kategorie, falls von der Gemeinde gefordert)
3. Versand per HTTP POST/SOAP an den Feratel-Endpunkt
4. Antwort auswerten: Erfolg → `FeratelMeldung.status = erfolgreich`; Fehler → Fehlercode speichern, in der UI als „zu prüfen“ markieren, Retry-Mechanismus
5. Reporting-Ansicht in der App: offene, erfolgreiche und fehlgeschlagene Meldungen auf einen Blick, mit manueller Nachbearbeitungsmöglichkeit

**Wichtig für die Datenqualität:** PLZ/Land des Gasts müssen korrekt erfasst werden, da Feratel daraus teils automatisch Codes ableitet – fehlerhafte PLZ kann laut Feratel-Dokumentation zu nicht übermittelbaren Meldescheinen führen. Das Formular sollte dies validieren (z. B. Pflichtfeld + Formatprüfung).

## 6. HESTA-Monatsmeldung (integriert, automatisch befüllt)

Die monatliche Meldung von Land, Anzahl Personen und Anzahl Übernachtungen (Grundlage für die eHESTA-Erhebung des BFS) wird **nicht mehr manuell erfasst**, sondern direkt aus den bereits vorhandenen `Aufenthalt`- und `Rechnung`-Daten generiert. Das PDF-Formular aus Abschnitt 5 wird damit vom Erfassungsformular zum **automatisch ausgefüllten Report/Beleg**.

### 6.1 Zusätzliche/angepasste Entität

| Entität | Zweck |
|---|---|
| `HestaMeldung` | Protokoll je Meldeperiode (Monat/Jahr): Zeitpunkt der Generierung, verwendeter Datenstand, Status (entworfen/exportiert/eingereicht), erzeugte PDF-Datei |
| `HestaMeldungPosition` | Aggregierte Zeile je Land für eine `HestaMeldung`: `land`, `anzahlPersonen`, `anzahlUebernachtungen` |

`Gast.land` (bzw. ein daraus abgeleiteter ISO-Ländercode) ist damit ein Pflichtfeld, da es sowohl für Feratel als auch für HESTA die zentrale Gruppierungsdimension ist.

### 6.2 Aggregationslogik

Für einen gewählten Meldemonat werden alle **abgerechneten** `Aufenthalte` herangezogen (nur Aufenthalte mit abgeschlossenem Check-out bzw. bezahlter/gestellter Rechnung, um Datenqualität sicherzustellen):

1. Gruppierung aller `Aufenthalte` des Monats nach `Gast.land`
2. Je Land:
   - `anzahlPersonen` = Anzahl distinkter Gäste mit mindestens einer Übernachtung im Meldemonat (bei Aufenthalten, die über den Monatswechsel gehen, zählt der Gast im Monat des Aufenthaltsbeginns – analog zur BFS-Definition „Ankünfte“)
   - `anzahlUebernachtungen` = Summe der auf den Meldemonat entfallenden Nächte je Aufenthalt (bei Aufenthalten über den Monatswechsel wird pro Kalendermonat anteilig gezählt)
3. Speicherung als `HestaMeldungPosition`-Datensätze unter einer neuen `HestaMeldung`

### 6.3 Verbindung zum PDF-Formular

Das in Abschnitt 5 erstellte Formular besitzt pro Land bereits benannte, befüllbare Felder (`personen_<land>`, `naechte_<land>` sowie `total_personen`/`total_naechte`). Der Report-Generator:

- ordnet jede `HestaMeldungPosition.land` einem stabilen internen Ländercode zu (nicht dem Anzeigetext, um Tippfehler/Umbenennungen robust zu machen)
- befüllt die entsprechenden PDF-Felder automatisch mit den aggregierten Werten
- berechnet die Total-Zeile serverseitig (Summenkontrolle, nicht durch den Benutzer)
- legt das erzeugte PDF unter `HestaMeldung.dokument` ab und markiert die Meldung als „bereit zur Übermittlung“

Der manuelle Erfassungsschritt entfällt damit vollständig; das Formular dient nur noch als **Beleg/Kontrolldokument**, das 1:1 in eHESTA übertragen (oder später direkt maschinell übermittelt) werden kann.

### 6.4 Prozessschritt „Monatsabschluss“

1. Am Monatsende (oder auf Knopfdruck) wählt die Verwaltung „HESTA-Meldung erzeugen“ für den Vormonat
2. System prüft, ob alle Aufenthalte des Zeitraums abgerechnet/abgeschlossen sind (sonst Warnung: „X offene Aufenthalte“)
3. Aggregation gemäss 6.2, automatische PDF-Befüllung gemäss 6.3
4. Verwaltung kontrolliert die Zahlen im generierten PDF, gibt frei
5. PDF dient als Beleg für die Eingabe auf eHESTA (Zwischenschritt) bzw. wird in Phase 2 direkt maschinell übermittelt

## 7. Kernprozess (End-to-End)

1. **Reservationsanfrage** → Eingang (E-Mail/Homepage), Vollständigkeitsprüfung, Erstantwort mit Zahlungsinfos, nach Zahlungsbestätigung automatische Umwandlung in `Buchung` (Abschnitt 10)
2. **Buchung anlegen** → Stellplatz, Zeitraum, Hauptgast (direkt oder aus Reservationsanfrage)
3. **Check-in** → Erfassung aller mitreisenden Gäste (Aufenthalte), Ausweis-/Altersdaten
4. **Aufenthalt** (automatisch laufend im System)
5. **Check-out** → Berechnung Übernachtung + Taxen anhand `Artikel`/`ArtikelPreis` (saisonabhängig) → Rechnung mit MWST-Ausweis je Satz (Abschnitt 9)
6. **Feratel-Meldung** → automatischer XML/SOAP-Versand, Statusverfolgung
7. **Monatsabschluss** → automatische HESTA-Aggregation & PDF-Befüllung (Abschnitt 6), Kontrolle/Freigabe
8. **Reporting** → Abgleich eigene Abrechnung vs. Feratel-Meldungen vs. HESTA-Meldung, Exportmöglichkeit für Kontrollzwecke

## 9. Mehrwertsteuer (MWST) – zentrale Verwaltung

### 9.1 Grundprinzip

Der MWST-Satz wird **nicht** auf jedem Artikel als Zahl hinterlegt, sondern zentral als eigener Datensatz (`Mwstsatz`) gepflegt und von den Artikeln nur **referenziert**. Ändert sich ein Satz gesetzlich, wird ein neuer `Mwstsatz`-Datensatz mit neuem Gültigkeitsbeginn angelegt – alle Artikel, die auf den entsprechenden `code` (z. B. `BEHERBERGUNG`) zeigen, übernehmen den neuen Satz automatisch für künftige Rechnungen, ohne dass jeder Artikel einzeln angepasst werden muss.

> **Hinweis zur Genauigkeit:** Der von dir genannte Beherbergungssatz von 3.6 % war zwischen 2018–2023 gültig. Aktuell (seit 1.1.2024, unverändert 2026) beträgt der Schweizer MWST-Sondersatz für Beherbergung **3.8 %**, befristet bis Ende 2027. Da der Satz zentral und mit Gültigkeitsdatum abgelegt wird, ist das im Betrieb jederzeit korrigierbar – ich würde empfehlen, beim Aufsetzen der echten Daten den aktuell gültigen Satz mit deinem Treuhänder/der ESTV-Website zu verifizieren.

### 9.2 Zuordnung MWST-Satz → Artikel (Vorschlag)

Massgebend ist die Art der Leistung, nicht die Kategorie „Camping" als Ganzes. Grobe Einordnung nach den auf camping-aeschi.ch publizierten Positionen:

| Artikel | MWST-Kategorie (Vorschlag) | Begründung |
|---|---|---|
| Erwachsene / Kinder (Person/Nacht) | Beherbergung (Sondersatz) | Bestandteil der Übernachtungsleistung |
| Camper / Wohnwagen / Zelt (Stellplatz/Nacht) | Beherbergung (Sondersatz) | Standplatzmiete gilt als Teil der Beherbergungsleistung |
| Zwärgli / Spycher (Unterkunft/Nacht) | Beherbergung (Sondersatz) | Vermietete Unterkunftseinheit |
| Kurtaxe | **Ausgenommen** (kein MWST-Objekt) | Durchlaufender Posten, im Namen der Gemeinde eingezogen |
| Kantonale Beherbergungsabgabe | **Ausgenommen** (kein MWST-Objekt) | Durchlaufender Posten (Marketingbeitrag Kanton) |
| Auto / Motorrad | Normalsatz | Keine Übernachtungsleistung im engeren Sinn |
| Elektrische Energie | Normalsatz | Separate Lieferung (Strom) |
| Umweltabgabe | Normalsatz *(zu prüfen)* | Betriebseigene Gebühr, keine amtliche Taxe |
| Wassertankfüllung | Normalsatz | Separate Dienstleistung |

⚠️ Diese Zuordnung ist eine plausible Ersteinschätzung nach den allgemeinen MWST-Grundsätzen (Art. 25 MWSTG), **kein verbindlicher Steuerentscheid**. Vor dem produktiven Einsatz sollte sie mit einem Treuhänder/der ESTV abgeglichen werden – falsche Sätze bei Auto/Strom/Umweltabgabe wirken sich direkt auf die MWST-Abrechnung aus.

### 9.3 Artikelkatalog mit saisonalen Preisen (Quelle: camping-aeschi.ch/preise-2, Stand 2026)

**Hauptsaison** (1. Juli – 30. August 2026)

| Artikel | Preis | MWST-Kategorie |
|---|---|---|
| Erwachsene | CHF 8.00 | Beherbergung |
| Kinder | CHF 4.00 | Beherbergung |
| Kleinkinder (2–5 Jahre) | gratis | – |
| Camper | CHF 18.00 | Beherbergung |
| Wohnwagen | CHF 17.00 | Beherbergung |
| Zelt | CHF 14.00 | Beherbergung |
| Auto | CHF 3.00 | Normalsatz |
| Motorrad | CHF 2.00 | Normalsatz |

**Vor-/Nachsaison** (1. Mai – 30. Juni & 31. August – 30. September 2026)

| Artikel | Preis | MWST-Kategorie |
|---|---|---|
| Erwachsene | CHF 7.00 | Beherbergung |
| Kinder | CHF 3.40 | Beherbergung |
| Kleinkinder (2–5 Jahre) | gratis | – |
| Camper | CHF 16.00 | Beherbergung |
| Wohnwagen | CHF 15.00 | Beherbergung |
| Zelt | CHF 12.00 | Beherbergung |
| Auto | CHF 3.00 | Normalsatz |
| Motorrad | CHF 1.70 | Normalsatz |

**Saisonunabhängige Zusatzpositionen**

| Artikel | Preis | MWST-Kategorie |
|---|---|---|
| Kurtaxe Erwachsene | CHF 3.50 | Ausgenommen |
| Kurtaxe Kinder | gratis | – |
| Elektrische Energie | CHF 4.00 | Normalsatz |
| Umweltabgabe | CHF 1.00 | Normalsatz *(zu prüfen)* |
| Wassertankfüllung (bei 1 Nacht; ab 2 Nächten inkl.) | CHF 5.00 | Normalsatz |
| Zwärgli (2 Personen/Nacht) | CHF 40.00 | Beherbergung |
| Spycher (2 Personen/Nacht) | CHF 60.00 | Beherbergung |

Diese Tabelle bildet die Ausgangsbefüllung von `Artikel` + `ArtikelPreis` (je Artikel zwei `ArtikelPreis`-Datensätze für Haupt- bzw. Vor-/Nachsaison, die saisonunabhängigen Positionen ohne Saisonbezug bzw. mit einer „ganzjährig"-Saison).

### 9.4 Berechnung auf der Rechnungsposition

1. Bei Rechnungsstellung wird für jeden `Artikel` der zum Leistungsdatum gültige `ArtikelPreis` (passend zur `Saison`) sowie der aktuell gültige `Mwstsatz` (über `Artikel.mwstsatzId`) ermittelt
2. `Rechnungsposition.mwstsatzProzent` wird mit diesem Wert befüllt (Snapshot, siehe 3.2)
3. `mwstBetrag = betrag − betrag / (1 + mwstsatzProzent / 100)` (MWST ist in Schweizer Konsumentenpreisen inklusive, daher Rückrechnung aus Bruttobetrag)
4. Auf der Rechnung werden die Positionen nach MWST-Satz gruppiert ausgewiesen (gesetzliche Pflicht: getrennter Ausweis je Steuersatz)

## 10. Reservationsanfragen – Workflow

### 10.1 Grundidee

Reservationsanfragen kommen heute per E-Mail rein, später eventuell auch strukturiert über ein Formular auf der Homepage. Beide Kanäle münden in derselben zentralen Entität `Reservationsanfrage`, damit die Verwaltung **einen** gemeinsamen Posteingang hat, unabhängig von der Quelle.

```
E-Mail-Postfach ──┐
                   ├──► Reservationsanfrage (zentral) ──► Prüfung vollständig? ──► Sammelliste "Offene Anfragen"
Homepage-Formular ─┘                                              │
                                                          nein ────┘── Rückfrage / manuelle Nachbearbeitung
```

- **E-Mail-Kanal (heute):** Eine Person liest die eingehende Mail und legt daraus eine `Reservationsanfrage` an bzw. das System unterstützt dies mit einer Erfassungsmaske (Copy-Paste-freundlich); der Rohtext der Mail wird zur Nachvollziehbarkeit mitgespeichert.
- **Homepage-Formular (später):** Felder sind von vornherein strukturiert, `Reservationsanfrage` wird automatisch erzeugt.
- In beiden Fällen prüft das System die Pflichtfelder (Zeitraum, Stellplatztyp, Personenzahl, Kontaktangaben) und setzt `vollstaendig = true/false` mit Liste der `fehlendeAngaben`. Nur vollständige Anfragen erscheinen in der zentralen Sammelliste zur Bearbeitung; unvollständige bleiben sichtbar, aber separat markiert (z. B. für eine Rückfrage an den Gast).

### 10.2 Erstantwort mit Zahlungsinformationen

1. Eine Mitarbeiterin/ein Mitarbeiter öffnet eine vollständige `Reservationsanfrage` und löst **manuell** „Erstantwort senden" aus (**kein** vollautomatischer Versand – der Mensch bleibt am Drücker, das System bereitet nur alles vor)
2. Das System schlägt Sprache und passende `EmailVorlage` (Typ „Erstantwort mit Zahlungsinformationen") vor; die Person kann die Sprache wechseln (DE/FR/IT/EN) und den Text vor dem Senden noch anpassen
3. Platzhalter werden automatisch befüllt (Gastname, Zeitraum, Stellplatztyp, voraussichtlicher Betrag anhand `Artikel`/`ArtikelPreis`/Saison, sowie ein **Zahlungsinformationen-Block**, der je nach verfügbarer(n) Zahlungsart(en) unterschiedlich befüllt wird – siehe 10.4)
4. Versand wird als `EmailVersand` protokolliert, `Reservationsanfrage.status` wechselt auf `erstantwort-gesendet` bzw. `zahlung-ausstehend`

### 10.3 Vorlagenbibliothek (4 Sprachen)

- `EmailVorlage` ist je Kombination aus **Vorlagentyp** und **Sprache** ein eigener, unabhängig editierbarer Datensatz (z. B. 1 Typ × 4 Sprachen = 4 Vorlagen)
- Eine Verwaltungsansicht („Vorlagenbibliothek") erlaubt das Bearbeiten von Betreff und Text inkl. Platzhalter-Hilfe (Liste verfügbarer `{{Platzhalter}}` mit Beschreibung), ohne dass Entwicklung nötig ist
- Struktur ist so ausgelegt, dass später einfach weitere Vorlagentypen (Zahlungserinnerung, Absage, Bestätigung Check-in-Infos) ergänzt werden können, ohne das Datenmodell zu ändern

### 10.4 Zahlungsarten

Bei der Reservationsbestätigung stehen dem Gast drei Zahlungsarten zur Auswahl, die unterschiedlich weit automatisiert sind:

| Zahlungsart | Status in Phase 1 | Zahlungsabgleich | Hinweis im Mail-Platzhalter |
|---|---|---|---|
| Banküberweisung | aktiv | manuell (Kontoauszug/QR-Einzahlung prüfen) | IBAN, QR-Referenznummer, Zahlungsfrist |
| TWINT | aktiv | manuell (Zahlungseingang/Screenshot prüfen) | TWINT-Nummer bzw. QR-Code |
| Kreditkarte | **vorgesehen, aktuell inaktiv** | *(später automatisch via Zahlungsanbieter-Webhook)* | Aktuell **nicht** im Mailtext aufgeführt, solange `Zahlungsanbieterkonfiguration.aktiv = false` |

- Jede `Zahlung` trägt ein `zahlungsart`-Feld; Banküberweisung/TWINT werden heute ausschliesslich manuell von einer Person auf „eingegangen" gesetzt (Abschnitt 10.5)
- Für Kreditkarte ist die Datenstruktur (`Zahlung`, `Zahlungsanbieterkonfiguration`) bereits vorhanden, aber **nicht produktiv**: Es existiert noch kein Anbietervertrag/keine API-Anbindung. Der Mailtext-Platzhalter blendet die Option automatisch aus, solange die Konfiguration inaktiv ist – kein manueller Anpassungsaufwand nötig, sobald sie später aktiviert wird
- Bei künftiger Aktivierung: Kartenzahlung läuft über einen Checkout-Link im Mail, der Zahlungsanbieter bestätigt per Webhook automatisch, `Zahlung.status` wechselt ohne manuelles Zutun auf „eingegangen", was Schritt 10.5.2 (manuelle Prüfung) für diese Zahlungsart überflüssig macht

### 10.5 Bestätigung der Zahlung → Akzeptierte Reservation

1. Zahlungseingang wird geprüft — bei Banküberweisung/TWINT in der ersten Ausbaustufe **manuell** (Kontoauszug/QR-Einzahlung bzw. TWINT-Beleg prüfen), bei Kreditkarte **später automatisch** sobald aktiviert (siehe 10.4)
2. Person markiert die zugehörige `Zahlung` als „eingegangen" (bzw. dies geschieht künftig bei Kreditkarte automatisch via Webhook)
3. Sobald der offene Betrag der `Reservationsanfrage` gedeckt ist, erzeugt das System automatisch die `Buchung` (verknüpft über `reservationsanfrageId`) und setzt `Reservationsanfrage.status = bezahlt-akzeptiert`
4. Ab hier läuft die Reservation im bereits bestehenden Kernprozess weiter (Abschnitt 7: Check-in, Aufenthalt, Abrechnung, Feratel-Meldung …)
5. Die Reservation ist damit im System klar als **akzeptiert** ersichtlich, unterscheidbar von noch offenen/unbezahlten Anfragen

### 10.6 Übersicht der Reservationen (Monat/Woche/Zeitraum)

Eine Übersichtsansicht zeigt `Buchungen` (bestätigt/akzeptiert) sowie optional offene `Reservationsanfragen` mit folgender Filterung:

- **Dropdown „Ansicht"**: Monat / Woche / freier Zeitraum
- Bei „Monat"/„Woche": Vor-/Zurück-Navigation plus Schnellsprung „heute"
- Bei „freier Zeitraum": zwei Datumsfelder (Von/Bis) für individuelle Auswertungen (z. B. Saisonvergleich)
- Darstellung als Liste und/oder Belegungskalender (Stellplätze × Zeitachse), mit Filter nach Status (alle / nur akzeptiert / nur offene Anfragen)
- Dient sowohl der Tagesarbeit (Wer kommt diese Woche?) als auch der Auswertung (Wie viele Reservationen im Juli?)

### 10.7 Spätere Homepage-Anbindung (noch offen)

Wie eine Reservationsanfrage künftig **direkt von der Homepage** ins Verwaltungstool gelangt, ist bewusst noch nicht entschieden – das Datenmodell (`Reservationsanfrage.quelle = Homepage-Formular`) ist aber bereits so angelegt, dass alle drei realistischen Varianten ohne Strukturänderung möglich sind:

| Option | Funktionsweise | Vorteil | Nachteil |
|---|---|---|---|
| **A – Eigenes Formular + API** | Buchungsformular auf der Website sendet die Daten direkt strukturiert an eine Schnittstelle des Verwaltungstools | Volle Kontrolle, sofort strukturierte Daten, kein Medienbruch | Website-seitige Entwicklung/Wartung nötig |
| **B – Drittanbieter-Buchungswidget** | Ein bestehendes Buchungs-/Anfrage-Widget (z. B. eines Website-Baukastens oder Channel-Managers) leitet Anfragen per Webhook oder E-Mail weiter | Schnell einsetzbar, wenig Eigenentwicklung | Laufende Abhängigkeit/Kosten beim Anbieter, ggf. eingeschränkte Feldstruktur |
| **C – Formular-Plugin per E-Mail** | Bestehendes Kontaktformular-Plugin der Website (z. B. bei WordPress) sendet strukturierte Anfragen per E-Mail – landet im bereits vorgesehenen E-Mail-Kanal (Abschnitt 10.1) | Kleinster Umsetzungsschritt, nutzt den ohnehin vorhandenen Posteingang, keine neue technische Schnittstelle | Kein „echter" Automatisierungsgewinn gegenüber heute – Vollständigkeitsprüfung bleibt (teil-)manuell |

Unabhängig von der späteren Wahl ändert sich am Kernmodell (`Reservationsanfrage`, Vollständigkeitsprüfung, Erstantwort-Workflow) nichts – nur die Art, wie der Datensatz befüllt wird, unterscheidet sich. Die Entscheidung kann daher zu einem späteren Zeitpunkt getroffen werden, ohne bereits gebaute Teile der Software zu verwerfen.

## 11. Newsletter

### 11.1 Wichtiger Hinweis zur Einwilligung (bitte vor der Umsetzung beachten)

Nur weil eine E-Mail-Adresse aus einer `Reservationsanfrage` vorliegt, darf sie **nicht automatisch** für Newsletter-Marketing verwendet werden. Nach Schweizer Recht (revDSG sowie UWG Art. 3 Abs. 1 lit. o zu unerwünschter Massenwerbung) braucht es entweder:

- eine **ausdrückliche Einwilligung** (Opt-in, z. B. separat ankreuzbare Checkbox „Ich möchte den Newsletter erhalten" bei der Reservationsanfrage – **nicht** vorangehakt), oder
- die enger gefasste Ausnahme für **bestehende Kundenbeziehungen** bei ähnlichen eigenen Produkten/Dienstleistungen, wobei auch dort bei **jeder** E-Mail unmissverständlich und kostenlos abgemeldet werden können muss

Das Datenmodell trägt dem Rechnung, indem `newsletterEinwilligung` an der `Reservationsanfrage` **bewusst getrennt** von der eigentlichen Buchungsanfrage erfasst wird (kein Pflichtfeld, keine Vorauswahl), und jedes `NewsletterAbo` seine Einwilligungsquelle und Zeitpunkt dokumentiert – das ist im Streitfall die Nachweisgrundlage. Ich würde empfehlen, den genauen Wortlaut der Checkbox und die Ausgestaltung kurz mit einer Fachperson (Treuhänder/Datenschutzberatung) abzugleichen, bevor die erste Kampagne verschickt wird.

### 11.2 Aufbau des Adressbestands

- Bei jeder `Reservationsanfrage` (und optional beim Check-in) kann der Gast separat in den Newsletter einwilligen
- Bei Einwilligung wird automatisch (oder bei bereits bestehender Adresse: aktualisiert) ein `NewsletterAbo` angelegt – unabhängig von der einzelnen Buchung, damit ein Gast auch nach Jahren mit derselben Adresse wiedererkannt wird
- Sprachzuordnung (`NewsletterAbo.sprache`) übernimmt primär die bei der Reservation verwendete Sprache, ist aber vom Gast/der Verwaltung änderbar

### 11.3 Versand über Mailchimp

Der eigentliche Newsletter-Versand erfolgt **nicht** aus der Campingverwaltung selbst, sondern über **Mailchimp** – das übernimmt Zustellbarkeit, Bounce-Handling, Abmeldelinks und die eigentliche Kampagnengestaltung/-statistik (Öffnungs-/Klickraten), was für eine selbstgebaute Lösung unverhältnismässig aufwändig wäre.

- Unser System bleibt die **führende Quelle für die Einwilligung** (`NewsletterAbo`), Mailchimp die **führende Quelle für Versand/Statistik**
- Bei Einwilligung wird der Kontakt automatisch per Mailchimp-API zur konfigurierten `audienceId` hinzugefügt (inkl. Merge-Feld/Tag für die Sprache, damit z. B. deutschsprachige und französischsprachige Gäste getrennt angeschrieben werden können)
- Eine Abmeldung kann an zwei Stellen passieren: über den Mailchimp-Abmeldelink in der Mail (Mailchimp informiert unser System per Webhook zurück → `NewsletterAbo.status = abgemeldet`) oder direkt in unserer Verwaltung (wird per API an Mailchimp zurückgemeldet) — die beiden Systeme bleiben so synchron
- Die eigentliche Kampagnenerstellung (Text, Layout, Versandzeitpunkt) kann entweder direkt in Mailchimp erfolgen, oder – falls gewünscht – aus der Campingverwaltung heraus angestossen werden (`NewsletterKampagne` wird per API als Mailchimp-Kampagne angelegt); das ist ein UX-Detail, das in der Umsetzungsphase entschieden werden kann und das Datenmodell nicht verändert

### 11.4 Voraussetzungen für die Mailchimp-Anbindung

- Mailchimp-Konto und eine dedizierte **Audience** für den Camping-Newsletter einrichten
- API-Key generieren und in `MailchimpKonfiguration` hinterlegen (verschlüsselt)
- In Mailchimp die Merge-Felder/Tags für Sprache (DE/FR/IT/EN) anlegen, damit sprachspezifische Kampagnen möglich sind
- Double-Opt-in-Einstellung in Mailchimp mit der lokalen Einwilligungslogik abstimmen (siehe 11.1) – im Regelfall reicht die bereits bei uns dokumentierte Einwilligung als Single-Opt-in in Mailchimp, ein zusätzliches Double-Opt-in in Mailchimp wäre eine zweite, u. U. verwirrende Bestätigung für den Gast

## 12. Rechnungsversand per E-Mail (PDF)

### 12.1 Ablauf

1. Bei/nach Check-out wird die `Rechnung` inkl. aller `Rechnungspositionen` (Übernachtung, Taxen, Zusatzleistungen – je mit korrektem MWST-Satz gemäss Abschnitt 9) erzeugt und als PDF gerendert (`Rechnung.pdfPfad`), analog zur bereits konzipierten PDF-Erzeugung bei der HESTA-Meldung
2. Das PDF enthält die gesetzlich für Schweizer Rechnungen nötigen Angaben: Rechnungsnummer, Datum, Leistungsdatum/-zeitraum, MWST-Nummer des Betriebs, Aufschlüsselung nach Steuersatz (Beherbergung/Normalsatz/Ausgenommen), Zahlungsinformationen
3. Eine Person kann die Rechnung direkt aus der Buchung/Rechnungsansicht per Klick als E-Mail versenden (analog zum Reservations-Erstantwort-Workflow, Abschnitt 10.2): System schlägt Sprache (aus `Gast`/`Reservationsanfrage`) und passende `EmailVorlage` (Typ „Rechnung") vor, befüllt Platzhalter, hängt das PDF an
4. Versand wird als `EmailVersand` (mit `bezugTyp = rechnung`) protokolliert; `Rechnung.versendetAm` wird gesetzt

### 12.2 Zahlungsmethoden bei Rechnungsstellung

Bei der Vor-Ort-/Schlussabrechnung stehen **Bar, TWINT und Kreditkarte** zur Verfügung (zusätzlich zur bereits in Abschnitt 10.4 beschriebenen Banküberweisung für die Reservations-Anzahlung):

| Zahlungsart | Einsatz | Abgleich |
|---|---|---|
| Bar | Vor-Ort-Zahlung bei Check-out | direkt durch die Person erfasst, keine externe Bestätigung nötig |
| TWINT | Vor-Ort oder per Zahlungslink | manuell bestätigt (analog 10.4), später ggf. automatisiert |
| Kreditkarte | Vor-Ort (Terminal) oder online | **wie in Abschnitt 10.4**: Struktur vorbereitet (`Zahlungsanbieterkonfiguration`), Aktivierung noch offen |

Jede Zahlung wird als `Zahlung` mit `bezugTyp = rechnung` erfasst; eine Rechnung gilt als beglichen, sobald die Summe ihrer `Zahlungen` dem `gesamtbetrag` entspricht.

## 13. Auswertungen / Reporting

Aufbauend auf `Rechnung`, `Rechnungsposition` und `Zahlung` sind folgende Auswertungen vorgesehen, jeweils mit demselben Zeitraum-Auswahlmuster wie in Abschnitt 10.6 (Dropdown Monat/Woche/freier Zeitraum mit Datumsfeldern):

| Auswertung | Datengrundlage | Gruppierung |
|---|---|---|
| **Umsatz nach Kunde** | `Rechnung.gesamtbetrag` | gruppiert nach `Rechnung.kundeId` |
| **Umsatz pro Monat/Zeitraum** | `Rechnung.gesamtbetrag` bzw. `Rechnungsposition.betrag` | gruppiert nach Monat oder frei wählbarem Zeitraum |
| **Auswertung nach Artikel** | `Rechnungsposition.betrag`/`menge` | gruppiert nach `Artikel` (z. B. wie viel Umsatz durch Übernachtungen vs. Strom vs. Kurtaxe) |
| **Zahlungsmethoden über Zeitraum** | `Zahlung.betrag` | gruppiert nach `zahlungsart` (Bar/TWINT/Kreditkarte/Banküberweisung), z. B. als Balken-/Kreisdiagramm je Monat |

- **Darstellung:** direkt im Programm als Tabelle/Liste sowie als Diagramm (z. B. Balken für Umsatz pro Monat, Kreisdiagramm für Zahlungsmethoden-Anteile)
- **Export:** wahlweise als **PDF** (formatierter Bericht, z. B. für Ablage/Weitergabe) oder als **Excel** (`.xlsx`, für Weiterverarbeitung/Buchhaltung), pro Auswertung wählbar
- Alle Auswertungen filterbar nach Status (nur bezahlte Rechnungen / inkl. offene)
- Die MWST-Aufschlüsselung aus Abschnitt 9.4 (Gruppierung nach Steuersatz) lässt sich mit denselben Bausteinen als weitere Auswertung („MWST-Abrechnung je Periode") realisieren – relevant für die eigene MWST-Abrechnung ans ESTV

## 14. Offene Punkte für die nächste Phase

- Aktuell gültigen MWST-Beherbergungssatz mit Treuhänder/ESTV verifizieren (3.6 % vs. 3.8 %) und die Zuordnung in 9.2 (insb. Umweltabgabe, Auto/Motorrad) bestätigen lassen
- Exakte aktuelle Taxensätze (Kurtaxe Aeschi, kantonale Beherbergungsabgabe) und ggf. Sonderregelungen bei Thun-Thunersee Tourismus verifizieren
- Genaue XML-Struktur/WSDL der Feratel „Deskline 3.0 VT PMS Web Services“ anfordern (nicht öffentlich einsehbar, wird nach PMS-Partner-Freischaltung bereitgestellt)
- Entscheidung: synchroner Versand bei Check-out oder Batch-Job
- Exakte BFS-Definition für monatsübergreifende Aufenthalte (Ankünfte/Logiernächte-Zuordnung) mit HESTA-Wegleitung abgleichen
- Konkrete Wahl des Kreditkarten-/Zahlungsanbieters (z. B. Saferpay, Datatrans, Stripe) treffen, sobald die KK-Integration aktiviert werden soll – inkl. Vertrag, Gebühren, Anbindungsaufwand
- Entscheidung zur Homepage-Anbindung (Option A/B/C aus Abschnitt 10.7) treffen, sobald die Website-Seite dafür bereit ist
- Genauen Wortlaut/Ausgestaltung der Newsletter-Einwilligung (Checkbox-Text, Double-Opt-in ja/nein) mit Datenschutzberatung abstimmen
- Mailchimp-Konto/Audience/API-Key einrichten und Merge-Felder für die Sprachen anlegen
- Entscheiden, ob Kampagnen künftig direkt in Mailchimp oder aus der Campingverwaltung heraus erstellt werden (Abschnitt 11.3)
- Technologie-Stack für Umsetzung (z. B. Backend-Sprache, DB) festlegen

---

*Dies ist ein konzeptionelles Grobmodell als Diskussionsgrundlage – Feldnamen, Kardinalitäten und Prozessdetails werden in der nächsten Phase verfeinert.*
