# Basis-Image explizit auf Debian 13 (trixie) festgelegt, damit klar ist,
# aus welcher Distribution die CA-Zertifikate stammen. "python:3.12-slim"
# zeigt derzeit ebenfalls auf trixie, kann aber künftig wechseln.
# Für reproduzierbare Builds zusätzlich per Digest pinnen:
#   docker buildx imagetools inspect python:3.12-slim-trixie
#   FROM python:3.12-slim-trixie@sha256:<digest>
FROM python:3.12-slim-trixie

# Hochzählen (oder per --build-arg setzen), um die CA-Schicht unabhängig
# vom Docker-Cache neu zu bauen, z.B. nach einer neuen Debian-Sicherheits-
# meldung zu ca-certificates. Siehe docs/sicherheit-ca-zertifikate.md.
ARG CA_CERTS_REFRESH=2026-10-24

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# CA-Zertifikate über die offizielle Debian-Paketverwaltung aktualisieren
# (Quellen trixie, trixie-updates, trixie-security). Mindestversion
# 20250419+deb13u1 = DSA-6572-1 (eMudhra-Vorfall: entfernt
# "emSign ECC Root CA - G3" und "AAA Certificate Services").
# update-ca-certificates --fresh baut /etc/ssl/certs vollständig neu auf,
# damit keine veralteten Symlinks zurückbleiben.
# Bewusst ohne feste Paketversion (immer neuester Sicherheitsstand), dafür
# mit Mindestversion per dpkg --compare-versions.
# hadolint ignore=DL3008
RUN echo "CA-Aktualisierung: ${CA_CERTS_REFRESH}" \
 && apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates openssl \
 && update-ca-certificates --fresh \
 && CA_VERSION="$(dpkg-query -W -f='${Version}' ca-certificates)" \
 && echo "ca-certificates ${CA_VERSION}" \
 && dpkg --compare-versions "${CA_VERSION}" ge "20250419+deb13u1" \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Vertrauensspeicher im Image prüfen: System-Bundle, /etc/ssl/certs,
# /etc/ssl/cert.pem (falls vorhanden) und das von certifi mitgelieferte
# Bundle (wird von httpx verwendet). Prüft die tatsächlichen Schlüssel-
# parameter und bricht den Build bei Befunden ab.
# (Wortaufteilung von $pfade ist hier beabsichtigt.)
COPY scripts/check_ca_bundle.py /usr/local/bin/check_ca_bundle.py
# hadolint ignore=SC2086
RUN set -e; \
    pfade="/etc/ssl/certs $(python -c 'import certifi; print(certifi.where())')"; \
    [ -e /etc/ssl/cert.pem ] && pfade="$pfade /etc/ssl/cert.pem"; \
    python -I /usr/local/bin/check_ca_bundle.py --strict-aaa $pfade

# Keine verwundbare Node.js-Laufzeit im Image (Node2Shell, CVE-2026-111497,
# und weitere Fixes vom 21.10.2026). Das Image braucht kein Node.js. Die
# Prüfung schlägt an, falls ein Base Image oder ein Python-Paket (z.B. mit
# eingebettetem Node wie playwright) eine alte Version mitbringt.
COPY scripts/check_node_versions.py /usr/local/bin/check_node_versions.py
RUN python -I /usr/local/bin/check_node_versions.py /

COPY . .

# Keine zusätzlichen (veralteten) Zertifikats-Bundles mit dem Quellcode
# ins Image übernehmen (z.B. aus einer lokalen .venv) - siehe .dockerignore.
RUN set -e; \
    fremde="$(find /app -type f \( -name '*.pem' -o -name '*.crt' -o -name '*.cer' \))"; \
    if [ -n "$fremde" ]; then echo "Unerwartete Zertifikatsdateien im App-Verzeichnis:"; echo "$fremde"; exit 1; fi

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head || echo 'WARNUNG: Datenbankmigration fehlgeschlagen' >&2; exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
