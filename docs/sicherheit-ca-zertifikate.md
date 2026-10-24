# CA-Zertifikate im Docker-Image – Prüfung zum eMudhra-Vorfall (Oktober 2026)

Stand: 24.10.2026

## 1. Worum es geht – und eine Korrektur

Am 17.10.2026 wurde gemeldet, dass acht Zwischen-CAs von eMudhra
(Hierarchie „emSign … G3“) mit trivialen privaten Schlüsseln erzeugt
wurden. Gemeldet hat das ein externer Forscher, nicht eMudhra selbst;
eMudhra hat danach eine Stellungnahme veröffentlicht.

**Wichtig:** Betroffen sind **keine RSA-Schlüssel**, sondern
**EC-Schlüssel auf der Kurve NIST P-384**. Die privaten Schlüssel waren die
Zahlen 4, 56, 66, 115, 155, 156, 230 und 237. Wer nach „schwachen
RSA-Schlüsseln“ sucht, findet dieses Problem deshalb nicht. Wir haben die
Angaben selbst nachgerechnet: Aus diesen acht Zahlen ergeben sich genau die
acht veröffentlichten SPKI-SHA-256-Werte (siehe Abschnitt 5, Test T3).

| Zwischen-CA | Ausgestellt von | privater Schlüssel |
|---|---|---|
| EM DV TLS CA - G3B / G3C | emSign Root TLS CA - G3 und AAA Certificate Services (Cross-Sign) | 156 / 230 |
| EM OV TLS CA - G3B / G3C | dito | 155 / 4 |
| EM EV TLS CA - G3B / G3C | dito | 115 / 56 |
| EM OV CS CA - G3B / G3C (Code Signing) | emSign Root CS CA - G3 und AAA Certificate Services | 66 / 237 |

Reaktionen, die für dieses Projekt zählen:

- Mozilla/NSS 3.131.1 und **certifi ≥ 2026.10.19** entfernen
  `emSign ECC Root CA - G3`.
- **Debian DSA-6572-1** liefert `ca-certificates 20250419+deb13u1` für
  Debian 13 (trixie). Dieses Update entfernt `emSign ECC Root CA - G3` und
  `AAA Certificate Services`.
- `emSign Root CA - G1` (RSA) bleibt vertrauenswürdig.

Quellen: Kudelski Security Advisory, The Hacker News, Keytos, Help Net
Security, LinuxSecurity (DSA-6572-1), eMudhra-Stellungnahme (Links in
Abschnitt 8).

## 2. Analyse des Images

| Element | Befund |
|---|---|
| Dockerfiles | nur eines: `Dockerfile`. Kein docker-compose, keine weiteren Images |
| Base Image | vorher `python:3.12-slim`, ohne Distribution angegeben (zeigt derzeit auf Debian 13 trixie), nicht gepinnt |
| System-Vertrauensspeicher | Debian-Paket `ca-certificates` aus dem Base Image. Das Dockerfile hat es **nie aktualisiert**: Es galt der Stand vom Bau des Base Images, und der Docker-Cache konnte diesen Stand beliebig lange halten |
| `/etc/ssl/certs/` | Symlinks plus `ca-certificates.crt`, erzeugt von `update-ca-certificates`. Python `ssl` bzw. OpenSSL nutzen diese Dateien (IMAP, SMTP) |
| `/etc/ssl/cert.pem` | gibt es unter Debian standardmässig nicht. Der Build prüft die Datei trotzdem, falls sie vorhanden ist |
| certifi | kommt als Abhängigkeit von httpx ins Image, war nicht gepinnt. Ein frischer Build hätte heute 2026.10.23 installiert (ok). Mit Cache oder Lockfile kann aber eine ältere Version im Image bleiben |
| **Kopierte Dateien** | Es gab **keine `.dockerignore`**. Deshalb kopierte `COPY . .` die lokale Windows-`.venv` ins Image, und darin liegt **certifi 2026.7.22 mit `emSign ECC Root CA - G3`** (Test T5). Mitkopiert wurden auch `.env` (Secrets) und `.git` |
| App-Code | `app/services/mail_import.py`: `imaplib.IMAP4_SSL(...)` wurde **ohne `ssl_context`** aufgerufen. Python verwendet dann einen Kontext **ohne Zertifikats- und Hostnamenprüfung**. Der IMAP-Import hat also überhaupt keinem CA-Bundle vertraut, sondern jedes Zertifikat akzeptiert (auch eines mit kompromittierter eMudhra-Kette). `app/services/mailversand.py` (SMTP) nutzt korrekt `ssl.create_default_context()` |

## 3. Betroffene bzw. geänderte Dateien

| Datei | Änderung |
|---|---|
| `Dockerfile` | Base Image `python:3.12-slim-trixie` angegeben. `ca-certificates` wird per `apt-get` aus den offiziellen Debian-Quellen (inkl. trixie-security) aktualisiert, danach `update-ca-certificates --fresh`. Mindestversion `20250419+deb13u1` wird geprüft (sonst bricht der Build ab). Build-Arg `CA_CERTS_REFRESH` erzwingt einen Neubau der Schicht. Der Build prüft alle Vertrauensspeicher mit `scripts/check_ca_bundle.py --strict-aaa`. Der Build bricht ab, wenn Zertifikatsdateien im App-Verzeichnis landen |
| `.dockerignore` (neu) | schliesst `.venv/`, `.env`, `.git`, Caches, `docs/` u.a. aus |
| `requirements.txt` | `certifi>=2026.10.19` (bewusst Untergrenze statt fester Version) |
| `scripts/check_ca_bundle.py` (neu) | Prüft PEM-Bundles anhand der echten Schlüsselparameter, nur mit der Standardbibliothek (Details unten) |
| `scripts/tls_probe.py` (neu) | TLS-Probe für den laufenden Container (Positiv- und Negativtest) |
| `app/services/mail_import.py` | `IMAP4_SSL(..., ssl_context=ssl.create_default_context())` |
| `tests/test_mail_import.py` | neuer Test: IMAP muss Zertifikat und Hostnamen prüfen |
| `README.md` | Hinweis im Abschnitt Infrastruktur |

### Was `check_ca_bundle.py` prüft

- SPKI-SHA-256 jedes Zertifikats gegen die 8 kompromittierten eMudhra-Schlüssel.
- **EC-Schlüssel:** Die Kurve muss bekannt sein (P-256/P-384/P-521), und der
  öffentliche Punkt darf nicht ±k·G für k < 65 536 sein. Damit wird genau
  die Schwäche aus diesem Vorfall direkt am Schlüssel erkannt, unabhängig
  von Namen oder Alter des Zertifikats.
- **RSA-Schlüssel:** Modul mindestens 2048 Bit, gültiger Exponent, keine
  kleinen Primfaktoren (< 20 000) und keine Faktorisierung nach Fermat
  (Primfaktoren zu nahe beieinander).
- Namensliste: emSign ECC Root CA - G3, emSign Root TLS/CS CA - G3 und die 8
  Zwischen-CAs. `AAA Certificate Services` gibt sonst eine Warnung aus, mit
  `--strict-aaa` gilt es als Befund.
- Exit-Code 0 = ok, 1 = Befund, 2 = Fehler (z.B. Pfad fehlt).

## 4. Keine unbeabsichtigten Entfernungen

- Es werden keine Zertifikate von Hand gelöscht. Was entfernt wird, legen
  allein die Paketbetreuer fest (Debian, certifi/Mozilla).
- Vergleich certifi 2026.7.22 → 2026.10.23: 121 → 118 Zertifikate, nichts
  kam dazu. Entfernt wurden `emSign ECC Root CA - G3`,
  `emSign ECC Root CA - C3` und `emSign Root CA - C1`. Den Grund für die
  beiden letzteren haben wir nicht einzeln geprüft. `emSign Root CA - G1`
  bleibt.
- Debian entfernt zusätzlich `AAA Certificate Services` (alte
  Sectigo/Comodo-Root). Gegenstellen, deren Kette noch **nur** über diese
  Root läuft, werden aus dem Container heraus nicht mehr verifiziert. Für
  die heute geplanten Gegenstellen (IMAP/SMTP-Provider, BFS, Mailchimp,
  Feratel) müssen Sie das mit `scripts/tls_probe.py` bzw. einem Test gegen
  den echten Server prüfen, sobald die Zugangsdaten vorliegen.

## 5. Durchgeführte Tests (in der Arbeitsumgebung von Claude)

| # | Test | Ergebnis |
|---|---|---|
| T1 | `check_ca_bundle.py` auf certifi 2026.7.22 | **NICHT OK**: `emSign ECC Root CA - G3` (P-384, SHA-256 `86A1ECBA…7A36BBE6B`), Exit 1 |
| T2 | `check_ca_bundle.py` auf certifi 2026.10.23 | OK: 118 Zertifikate, RSA 2048: 20, RSA 4096: 59, P-256: 3, P-384: 35, P-521: 1. Kein RSA-Schlüssel < 2048 Bit, kein trivialer EC-Schlüssel |
| T3 | Gegenprobe: P-384-Schlüssel mit d = 1…255 erzeugt, SPKI-Hashes verglichen | genau d = 4, 56, 66, 115, 155, 156, 230, 237 treffen die 8 veröffentlichten Hashes |
| T4 | Positivkontrolle mit künstlichen Zertifikaten (P-384 d=4, d=n−56, P-256 d=40000, RSA 1024, RSA mit nahen Primfaktoren, je ein starker RSA-/EC-Schlüssel) | alle schwachen erkannt, die starken nicht gemeldet. „AAA“: Warnung bzw. mit `--strict-aaa` Befund. Fehlender Pfad: Exit 2 |
| T5 | certifi-Bundle aus Ihrer lokalen `.venv` | identisch mit certifi 2026.7.22, **NICHT OK** (s. T1) |
| T6 | `FROM scratch`-Build nur mit dem Build-Kontext, mit und ohne `.dockerignore` | ohne: `.venv/.../cacert.pem`, `.env`, `.git` im Image. Mit: nichts davon |
| T7 | Prüfschritt aus dem Dockerfile nachgestellt (Python 3.12 venv, `pip install -r requirements.txt`) | certifi 2026.10.23 installiert, Prüfung OK. Negativprobe mit altem Bundle: Exit 1 |
| T8 | `dpkg --compare-versions` gegen Mindestversion | 20250419 → Abbruch, 20250419+deb13u1 → ok, 20260601 → ok, 20230311+deb12u1 → Abbruch |
| T9 | Projekttests (Python 3.12 und 3.13) | 38 bestanden (37 alt + 1 neu). Der neue IMAP-Test schlägt mit dem alten Code fehl und besteht mit dem neuen |
| T10 | `hadolint Dockerfile` | keine Befunde (DL3008 und SC2086 bewusst begründet unterdrückt) |

### Nicht durchgeführt – muss bei Ihnen laufen

Den **echten Image-Build** konnte Claude nicht ausführen. Die Arbeitsumgebung
darf weder Docker Hub (`python:3.12-slim-trixie`) noch die Debian-Spiegel
erreichen (Netzwerkrichtlinie, HTTP 403). Deshalb ist noch **nicht
nachgewiesen**, dass das gebaute Image die korrigierten Bundles enthält. Der
Build selbst bricht aber ab, wenn das nicht der Fall ist (Versionsprüfung
und `check_ca_bundle.py`).

Automatisch: Der GitHub-Workflow `.github/workflows/docker-ca-check.yml` führt Build,
Prüfung, TLS-Probe und Tests bei jedem Pull Request, bei Pushes auf `main`
und wöchentlich aus (ohne zu deployen).

Manuell auf einem Rechner mit Docker (PowerShell, im Projektordner):

```powershell
# 1. Ohne Cache und mit frischem Base Image bauen (veraltete Schichten vermeiden)
docker build --pull --no-cache -t campingverwaltung:ca-fix .

# 2. Stand im Image anzeigen
docker run --rm campingverwaltung:ca-fix sh -c "dpkg-query -W ca-certificates; python -c 'import certifi; print(certifi.__version__)'; ls /app/.venv 2>/dev/null || echo 'keine .venv im Image'"

# 3. Vertrauensspeicher erneut prüfen (läuft auch im Build)
docker run --rm campingverwaltung:ca-fix sh -c 'python -I /usr/local/bin/check_ca_bundle.py --strict-aaa /etc/ssl/certs $(python -c "import certifi; print(certifi.where())")'

# 4. TLS-Probe: normale Hosts müssen gehen, eMudhra-Testhosts müssen scheitern
docker run --rm campingverwaltung:ca-fix python scripts/tls_probe.py

# 5. Alte Images/Caches entfernen, damit nichts Veraltetes weiterläuft
docker builder prune -f
```

Erwartet: Schritt 1 läuft durch und meldet `ca-certificates 20250419+deb13u1`
(oder neuer). Schritte 3 und 4 enden mit `ERGEBNIS: OK`.

Zusätzlich die **lokale Entwicklungsumgebung** aktualisieren (betrifft nicht
das Image, aber Tests und lokale Aufrufe):

```powershell
.venv\Scripts\python -m pip install -U -r requirements.txt
```

## 6. Docker-Cache

- `ARG CA_CERTS_REFRESH` steht in der `RUN`-Zeile mit `apt-get`. Ein
  anderer Wert (`--build-arg CA_CERTS_REFRESH=2026-11-05`) baut die
  CA-Schicht neu, auch ohne `--no-cache`.
- `--pull` holt das aktuelle Base Image. Ohne diese Option bleibt ein lokal
  vorhandenes, altes `python:3.12-slim-trixie` in Gebrauch.
- Für reproduzierbare Builds das Base Image per Digest pinnen (Kommentar im
  Dockerfile) und den Digest bei jeder CA-Meldung bewusst erneuern.

## 7. Verbleibende Risiken / offene Punkte

1. **Echter Build und Laufzeittest stehen aus** (Abschnitt 5). Erst danach
   gilt das Problem im Image als behoben.
2. **Herkunft der Meldung:** Diese Prüfung stützt sich auf öffentliche
   Advisories. Falls Sie eine konkrete Meldung haben (z.B. vom Hoster
   Atoll, von einem Image-Scanner oder direkt von eMudhra), die tatsächlich
   **RSA**-Schlüssel oder andere Zertifikate nennt, schicken Sie sie bitte.
   Dann wäre das ein anderer Befund, und die Liste in `check_ca_bundle.py`
   muss ergänzt werden.
3. Die Entfernung von `AAA Certificate Services` durch Debian kann ältere
   Gegenstellen brechen (Abschnitt 4).
4. Python `ssl` prüft bei IMAP/SMTP keine Sperrlisten (CRL/OCSP). Schutz
   bietet also nur das Entfernen der Roots, keine Sperrprüfung zur Laufzeit.
5. Laufende Container und andere Umgebungen (Staging, Produktion bei
   Atoll) müssen neu ausgerollt werden. Ein neues Image allein ändert dort
   nichts.
6. `pytest`/`httpx` landen über `requirements.txt` auch im
   Produktions-Image. Das ist nicht Teil dieses Befunds; empfohlen wäre eine
   getrennte `requirements-dev.txt`.
7. Prüfen Sie auch den Windows-Host: Nur wenn die automatischen
   Root-/Disallowed-Zertifikatsupdates aktiv sind, ist der Host geschützt.

## 8. Quellen

- [Kudelski Security – eMudhra Intermediate CA Private Key Compromise](https://kudelskisecurity.com/research/emudhra-intermediate-ca-private-key-compromise)
- [The Hacker News – Eight eMudhra CA Keys Compromised](https://thehackernews.com/2026/10/eight-emudhra-ca-keys-compromised.html)
- [Keytos – eMudhra CA Key Compromise Explained](https://www.keytos.io/blog/pki/emudhra-ca-key-compromise/)
- [Help Net Security – eMudhra certificates private keys compromised](https://www.helpnetsecurity.com/2026/10/21/emudhra-certificates-private-keys-compromised/)
- [LinuxSecurity – Debian DSA-6572-1 ca-certificates](https://linuxsecurity.com/advisories/debian/debian-dsa-6572-1-ca-certificates)
- [eMudhra – Statement on Recent Certificate Security Incident](https://emudhra.com/en/post/certificate-security-incident)
