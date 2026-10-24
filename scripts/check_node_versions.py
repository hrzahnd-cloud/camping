#!/usr/bin/env python3
"""
Sucht Node.js-Laufzeiten und meldet Versionen, die von den Node.js-
Sicherheitsreleases vom 21.10.2026 noch nicht korrigiert sind, darunter
"Node2Shell" (CVE-2026-111497, Out-of-bounds-Write im Brotli-Decoder,
mögliche Remote Code Execution).

Quelle: https://nodejs.org/en/blog/vulnerability/october-2026-security-releases
Korrigiert sind 22.23.4, 24.22.1 und 26.12.1 sowie spätere Versionen
derselben Linie. Alle anderen Linien (20.x und älter, 21.x, 23.x, 25.x)
sind End-of-Life und gelten als betroffen.

Gesucht wird nach
  * ausführbaren Dateien "node"/"nodejs" im PATH und unter den angegebenen
    Verzeichnissen (Version per "--version"),
  * eingebetteten Bibliotheken "libnode.so*" (Version unbekannt, wird
    als Befund gemeldet, bis jemand sie geprüft hat).

Aufruf:  python3 check_node_versions.py [--warn-only] [VERZEICHNIS ...]
Exit-Code 0 = keine verwundbare Laufzeit gefunden (auch: gar keine
Node.js-Laufzeit), 1 = Befund (mit --warn-only immer 0).
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys

KORRIGIERT = {22: (22, 23, 4), 24: (24, 22, 1), 26: (26, 12, 1)}
NAMEN = {"node", "nodejs", "node.exe"}


def bewerte(version: str) -> tuple[bool, str]:
    """(verwundbar?, Begründung) für eine Versionsangabe wie 'v24.22.0'."""
    m = re.match(r"v?(\d+)\.(\d+)\.(\d+)", version.strip())
    if not m:
        return True, f"Version nicht lesbar: {version!r}"
    v = tuple(int(x) for x in m.groups())
    minimum = KORRIGIERT.get(v[0])
    if minimum is None and v[0] > max(KORRIGIERT):
        return False, "neuere Linie, erst nach den Oktober-2026-Fixes erschienen"
    if minimum is None:
        return True, f"Linie {v[0]}.x ohne Korrektur (End-of-Life/nicht unterstützt)"
    if v < minimum:
        return True, f"älter als {'.'.join(map(str, minimum))}"
    return False, f"korrigiert (>= {'.'.join(map(str, minimum))})"


def kandidaten(wurzeln):
    gefunden = set()
    for name in ("node", "nodejs"):
        pfad = shutil.which(name)
        if pfad:
            gefunden.add(os.path.realpath(pfad))
    libs = set()
    for wurzel in wurzeln:
        for verz, unterverz, dateien in os.walk(wurzel, onerror=lambda e: None):
            # virtuelle Dateisysteme überspringen
            unterverz[:] = [u for u in unterverz
                            if os.path.join(verz, u) not in ("/proc", "/sys", "/dev")]
            for datei in dateien:
                voll = os.path.join(verz, datei)
                if datei in NAMEN and os.path.isfile(voll) and os.access(voll, os.X_OK):
                    gefunden.add(os.path.realpath(voll))
                elif datei.startswith("libnode.so"):
                    libs.add(os.path.realpath(voll))
    return sorted(gefunden), sorted(libs)


def main(argv) -> int:
    warn_only = "--warn-only" in argv
    wurzeln = [a for a in argv if not a.startswith("--")]
    binaries, libs = kandidaten(wurzeln)
    befunde = 0
    if not binaries and not libs:
        print("Keine Node.js-Laufzeit gefunden.")
    for pfad in binaries:
        try:
            ausgabe = subprocess.run([pfad, "--version"], capture_output=True,
                                     text=True, timeout=20).stdout.strip()
        except (OSError, subprocess.SubprocessError) as exc:
            ausgabe = f"<Fehler: {exc}>"
        verwundbar, grund = bewerte(ausgabe)
        befunde += verwundbar
        print(f"{'VERWUNDBAR' if verwundbar else 'OK':10} {pfad}: {ausgabe} - {grund}")
    for lib in libs:
        befunde += 1
        print(f"{'PRÜFEN':10} {lib}: eingebettete Node.js-Bibliothek, Version manuell prüfen")
    print(f"ERGEBNIS: {'NICHT OK' if befunde else 'OK'} ({len(binaries)} Laufzeit(en), "
          f"{len(libs)} Bibliothek(en), {befunde} Befund(e))")
    if befunde and warn_only:
        return 0
    return 1 if befunde else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
