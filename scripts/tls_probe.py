#!/usr/bin/env python3
"""
TLS-Probe für den Container: prüft mit dem System-Vertrauensspeicher
(ssl.create_default_context, wie IMAP/SMTP der App) und optional mit
certifi (wie httpx), ob
  * normale Gegenstellen weiterhin verifiziert werden (Kette funktioniert),
  * Testhosts mit kompromittierten eMudhra-Zwischen-CAs abgelehnt werden.

Aufruf im Container:
    docker run --rm campingverwaltung python scripts/tls_probe.py

Exit-Code 0 nur, wenn alle Erwartungen erfüllt sind. Ein Netzwerkfehler
(z.B. keine Internetverbindung) zählt als "nicht geprüft" und führt zu
Exit-Code 2, nie zu einem falschen "OK".
"""
from __future__ import annotations

import socket
import ssl
import sys

# Muss funktionieren (Gegenstellen, die die App bzw. das Umfeld nutzt)
SOLL_OK = [
    "www.bfs.admin.ch",
    "pypi.org",
    "www.google.com",
]
# Muss scheitern: öffentliche Testhosts zum eMudhra-Vorfall
# (Kette über EM DV TLS CA - G3B, einmal via emSign-Root, einmal via
# Sectigo-Cross-Sign "AAA Certificate Services")
SOLL_FEHLER = [
    "dv-g3b-emudhra.we-have-a-problem.com",
    "dv-g3b-aaa-emudhra.we-have-a-problem.com",
]


def kontexte():
    yield "System (/etc/ssl/certs)", ssl.create_default_context()
    try:
        import certifi
    except ImportError:
        return
    yield f"certifi {certifi.__version__}", ssl.create_default_context(cafile=certifi.where())


def verbinde(kontext: ssl.SSLContext, host: str) -> str:
    """'ok', 'abgelehnt: …' oder 'netzwerk: …'."""
    try:
        with socket.create_connection((host, 443), timeout=10) as roh:
            with kontext.wrap_socket(roh, server_hostname=host) as tls:
                return f"ok ({tls.version()})"
    except ssl.SSLCertVerificationError as exc:
        return f"abgelehnt: {exc.verify_message}"
    except ssl.SSLError as exc:
        return f"abgelehnt: {exc}"
    except OSError as exc:
        return f"netzwerk: {exc}"


def main() -> int:
    fehler = ungeprueft = 0
    for name, kontext in kontexte():
        print(f"== {name}")
        for host, erwartung in [(h, "ok") for h in SOLL_OK] + [(h, "abgelehnt") for h in SOLL_FEHLER]:
            ergebnis = verbinde(kontext, host)
            if ergebnis.startswith("netzwerk"):
                status = "NICHT GEPRÜFT"
                ungeprueft += 1
            elif ergebnis.startswith(erwartung):
                status = "OK"
            else:
                status = "FALSCH"
                fehler += 1
            print(f"  [{status:13}] {host}: erwartet {erwartung}, ist {ergebnis}")
    if fehler:
        print("ERGEBNIS: NICHT OK")
        return 1
    if ungeprueft:
        print("ERGEBNIS: UNVOLLSTÄNDIG (Netzwerk)")
        return 2
    print("ERGEBNIS: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
