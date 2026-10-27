# Node.js „Node2Shell“ (CVE-2026-111497) – Prüfung

Stand: 24.10.2026

## 1. Die Schwachstelle (verifiziert)

Offizielle Quelle: [Node.js – Wednesday, October 21, 2026 Security Releases](https://nodejs.org/en/blog/vulnerability/october-2026-security-releases)

- **CVE-2026-111497**, Schweregrad **High**: Out-of-bounds-Write im
  Brotli-Decoder (`node:zlib`). Wer einer Anwendung Brotli-Daten zum
  Entpacken unterschieben kann, kann einen Absturz, ein Speicherleck oder
  Remote Code Execution auslösen.
- Betroffene Linien: **22.x, 24.x, 26.x**. Korrigierte Versionen:
  **22.23.4, 24.22.1, 26.12.1** (und spätere derselben Linie).
- End-of-Life-Linien (20.x und älter, 21.x, 23.x, 25.x) bekommen keine
  Korrektur und gelten laut Node.js bei jedem Sicherheitsrelease als
  betroffen.
- Mit demselben Release wurden weitere CVEs behoben, u.a. TLS-
  Hostnamenprüfung (CVE-2026-106069, CVE-2026-105483) und DNS
  (CVE-2026-105482). Die korrigierten Versionen schliessen alle.

Die Fachpresse nennt dieselben Versionen (Qualys, HeroDevs, Rescana;
Links in Abschnitt 7). Eine CVSS-Bewertung gab es zum Prüfzeitpunkt noch
nicht.

## 2. Wo im Projekt Node.js vorkommt

| Ort | Ergebnis |
|---|---|
| `Dockerfile` (Build und Runtime, einstufig, `python:3.12-slim-trixie`) | **kein Node.js vorgesehen**. Python-Anwendung, keine Node-Pakete installiert |
| Python-Abhängigkeiten (`requirements.txt`) | keine mit eingebettetem Node (geprüft an einer installierten Linux-Umgebung mit denselben Paketen: 0 Funde) |
| `frontend-prototyp/` | nur eine `.jsx`-Datei, kein `package.json`, kein Build, per `.dockerignore` nicht im Image. **Keine Node-Laufzeit** |
| `.nvmrc`, `package.json`, `engines`, Lockfiles | nicht vorhanden |
| CI `.github/workflows/docker-ca-check.yml` | **betroffen:** `actions/checkout@v4` läuft auf der **Node-20-Laufzeit** des GitHub-Runners (End-of-Life, keine Korrektur) |
| GitHub-Runner (`ubuntu-latest`) | bringt eigene Node-Versionen mit (Laufzeit für Actions, vorinstalliertes Node). Die verwaltet GitHub, nicht das Projekt |
| Atoll | baut das `Dockerfile`. Was Atolls eigene Infrastruktur verwendet, liegt nicht im Projekt |
| Claude-Desktop-App auf Ihrem PC (nicht Projekt) | meldet eingebettetes **Node 24.22.0** (Electron 44.9.3). Das liegt **unter 24.22.1**, also betroffen. Bitte die App aktualisieren |

## 3. Änderungen

| Datei | Änderung |
|---|---|
| `.github/workflows/docker-ca-check.yml` | `actions/checkout@v4` (node20) ersetzt durch `actions/checkout@v7.0.1`, per Commit-SHA `3d3c42e5…` gepinnt (Laufzeit node24), `persist-credentials: false`. Neue Schritte: Node-Versionen des Runners (als Hinweis) und **strikte Prüfung des finalen Runtime-Images** |
| `Dockerfile` | Build-Schritt `check_node_versions.py /`: Der Build bricht ab, sobald eine verwundbare Node.js-Laufzeit im Image auftaucht (z.B. durch ein anderes Base Image oder ein Python-Paket mit eingebettetem Node) |
| `scripts/check_node_versions.py` (neu) | sucht `node`/`nodejs` im PATH und im Dateisystem sowie `libnode.so*`, liest die Version und vergleicht mit 22.23.4 / 24.22.1 / 26.12.1. EOL-Linien gelten als verwundbar |
| `README.md` | Verweis auf dieses Dokument |

Ein Update von Node.js im Image war nicht nötig, weil es dort keins gibt.
Das Skript stellt sicher, dass das so bleibt.

## 4. Tests

| # | Test | Ergebnis |
|---|---|---|
| N1 | Skript mit 12 nachgebauten Versionen (Grenzwerte 22.23.3/22.23.4, 24.22.0/24.22.1, 26.12.0/26.12.1, EOL 20/21/23/25, neuere Linie 27) und einer `libnode.so` | alle Grenzfälle richtig, Exit 1 bei Befund, 0 ohne |
| N2 | Skript gegen echte Installationen in Claudes Arbeitsumgebung | hat echte Binärdateien erkannt, auch ein **in ein Python-Paket eingebettetes** Node (playwright, v24.21.0, verwundbar) |
| N3 | Python-Abhängigkeiten des Projekts (Linux, Python 3.12) | keine Node-Laufzeit |
| N4 | Projekttests | 38 bestanden |
| N5 | `hadolint Dockerfile`, `actionlint` Workflow | keine Befunde |
| N6 | `actions/checkout`: `action.yml` der Tags gelesen | v4 = `node20`, v6/v7.0.1 = `node24` |

### Nicht verifiziert

- **Echter Image-Build und Prüfung des finalen Runtime-Images:** In
  Claudes Umgebung ist Docker Hub gesperrt. Das erledigt der
  CI-Workflow, sobald die Änderungen auf GitHub sind (Commit/Push mit
  Ihrer Zustimmung). Bis dahin ist **nicht nachgewiesen**, dass das finale
  Image keine Node-Laufzeit enthält. Erwartet wird es aufgrund von Base
  Image und Abhängigkeiten.
- **Node-Version der GitHub-Runner:** Ob die node24-Laufzeit des Runners
  bereits 24.22.1 oder neuer ist, zeigt erst der CI-Lauf, als Warnung.
  Das Projekt kann das nicht beeinflussen.

## 5. Verbleibende Risiken

1. Die Runner-Laufzeit für Actions verwaltet GitHub. Falls die Warnung im
   CI erscheint, ist das ein Risiko bei GitHub, nicht in Ihrem Image.
   `actions/checkout` entpackt keine fremden Brotli-Daten, das praktische
   Risiko ist dort gering.
2. Falls künftig ein echtes Frontend mit Node-Build entsteht: Version per
   `.nvmrc`/`engines` festlegen (≥ 22.23.4, 24.22.1 oder 26.12.1), im
   Dockerfile einen mehrstufigen Build verwenden und Node nicht ins
   Runtime-Image übernehmen.
3. Eingebettete Laufzeiten auf Arbeitsrechnern (Claude-Desktop-App,
   VS Code, andere Electron-Apps) prüfen und aktualisieren.
4. `check_node_versions.py` kennt nur die Fixes vom 21.10.2026. Bei der
   nächsten Node-Sicherheitsmeldung muss die Tabelle `KORRIGIERT`
   nachgeführt werden.

## 6. Für Sie zum Ausführen (nach Push)

```powershell
docker build --pull --no-cache -t campingverwaltung:node-check .
docker run --rm campingverwaltung:node-check python -I /usr/local/bin/check_node_versions.py /
```
Erwartet: `Keine Node.js-Laufzeit gefunden.` und `ERGEBNIS: OK`.

## 6a. Nachtrag 27.10.2026: Bedienoberfläche

Seit der Bedienoberfläche (React) verwendet der Docker-Build Node.js, aber **nur in der
Build-Stufe** `node:24.22.1-trixie-slim` (korrigierte Version, Prüfung im Build). Das laufende
Image enthält weiterhin kein Node.js; `check_node_versions.py /` im Build und der CI-Schritt
„Node.js im finalen Runtime-Image“ stellen das sicher. `frontend/package.json` verlangt per
`engines` eine korrigierte Version, `frontend/.nvmrc` nennt 24.22.1.

## 7. Quellen

- [Node.js – October 2026 Security Releases (offiziell)](https://nodejs.org/en/blog/vulnerability/october-2026-security-releases)
- [Qualys – Node.js Patches Brotli RCE Flaw](https://blog.qualys.com/product-tech/2026/10/23/node-js-patches-brotli-remote-code-execution-flaw-find-vulnerable-runtimes-before-attackers-do)
- [HeroDevs – CVE-2026-111497 (Node2Shell)](https://www.herodevs.com/blog-posts/cve-2026-111497-node2shell-node-js-brotli-rce)
- [Rescana – Node2Shell, upgrade to 22.23.4, 24.22.1 or 26.12.1](https://www.rescana.com/post/nodejs-cve-2026-111497-node2shell-brotli-rce-october-2026)
- [actions/checkout](https://github.com/actions/checkout)
