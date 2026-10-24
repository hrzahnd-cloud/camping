#!/usr/bin/env python3
"""
Prüft CA-Zertifikats-Bundles auf unsichere bzw. vom eMudhra-Vorfall
(Oktober 2026) betroffene Zertifikate.

Hintergrund: Bei eMudhra wurden acht Zwischen-CA-Schlüssel (NIST P-384,
also EC und nicht RSA) mit trivialen privaten Schlüsseln (Werte < 256)
erzeugt. Die Zwischen-CAs hängen an "emSign Root TLS CA - G3" /
"emSign Root CS CA - G3" unter "emSign ECC Root CA - G3" sowie als
Sectigo-Cross-Signs an "AAA Certificate Services". Mozilla, Debian
(DSA-6572-1), Ubuntu (USN-8944-1) und certifi (>= 2026.10.19) haben
"emSign ECC Root CA - G3" entfernt, Debian zusätzlich
"AAA Certificate Services".

Das Skript verlässt sich nicht nur auf Namen oder Alter, sondern prüft
die tatsächlichen Schlüsselparameter jedes Zertifikats:
  * SPKI-SHA-256 gegen die acht bekannten kompromittierten Schlüssel
  * EC-Schlüssel: Kurve bekannt/sicher und öffentlicher Punkt != k*G für
    kleine k (erkennt genau die Art Schwäche aus dem eMudhra-Vorfall)
  * RSA-Schlüssel: Modulgrösse >= 2048 Bit, sinnvoller Exponent, keine
    kleinen Primfaktoren, keine nahe beieinanderliegenden Primfaktoren
    (Fermat)
  * Namensliste der betroffenen bzw. zurückgezogenen CAs

Nur Python-Standardbibliothek, damit es im schlanken Image läuft.

Aufruf:  python3 check_ca_bundle.py [--strict-aaa] PFAD [PFAD ...]
PFAD darf eine PEM-Datei (auch Bundle) oder ein Verzeichnis sein.
Exit-Code 0 = keine Befunde, 1 = Befunde, 2 = Fehler (z.B. Datei fehlt).
"""
from __future__ import annotations

import base64
import hashlib
import math
import os
import re
import sys

# --------------------------------------------------------------------------
# Bekannte Daten zum eMudhra-Vorfall (Quelle: Kudelski Security Advisory,
# Mozilla Bugzilla; Stand 2026-10-21)
# --------------------------------------------------------------------------
KOMPROMITTIERTE_SPKI_SHA256 = {
    "EBED6475C2C2D80FCB199F3FE8DD6E6B3CE60B77EB15D4E42C3DEC0C6F5B5105": "EM DV TLS CA - G3B",
    "49DD353DC2B919A3770645117D0E60C16115E7D1BC259EEFE734B00EA434FE5F": "EM DV TLS CA - G3C",
    "E0254C7FCDC265E2F0F8A428DABB75AB4AE039B4872D62F5EE57F0877D5A8A41": "EM EV TLS CA - G3B",
    "5C0660A2B164910D8FF589C18E14552E9E0EC237DCEFE2CB736D41A4811F81A0": "EM EV TLS CA - G3C",
    "EC4FFA1AD0AC88081314B7AAFFEF6A91F97CD57291BB5BA686C5415F5EB4F6B6": "EM OV CS CA - G3B",
    "92C063D67E8F14DB71D288E11266FFDAF69CBF115F7BAB14F3BC2F68D25E0E30": "EM OV CS CA - G3C",
    "43BFFA19D6EF651451F6841E019931E96F6F2EAEFF28AB4B6F1CE4576DE2717B": "EM OV TLS CA - G3B",
    "63ECEFEE431D49523BC1136C4E72D0206A477086CAF606CD5CF025686C109CF8": "EM OV TLS CA - G3C",
}

# CNs, die nicht (mehr) im Vertrauensspeicher stehen dürfen
VERBOTENE_CN = {
    "emSign ECC Root CA - G3",
    "emSign Root TLS CA - G3",
    "emSign Root CS CA - G3",
    "EM DV TLS CA - G3B", "EM DV TLS CA - G3C",
    "EM OV TLS CA - G3B", "EM OV TLS CA - G3C",
    "EM EV TLS CA - G3B", "EM EV TLS CA - G3C",
    "EM OV CS CA - G3B", "EM OV CS CA - G3C",
}
# Von Debian/Ubuntu (ältere Releases) zusätzlich entfernt; nicht jede
# Distribution/certifi hat das getan -> standardmässig nur Warnung.
AAA_CN = "AAA Certificate Services"

MIN_RSA_BITS = 2048
MAX_KLEINER_SKALAR = 1 << 16  # eMudhra-Schlüssel waren < 256

# --------------------------------------------------------------------------
# Elliptische Kurven (NIST, kurze Weierstrass-Form, a = -3)
# --------------------------------------------------------------------------
KURVEN = {
    "1.2.840.10045.3.1.7": ("P-256", dict(
        p=0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF,
        gx=0x6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296,
        gy=0x4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5)),
    "1.3.132.0.34": ("P-384", dict(
        p=int("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFE"
              "FFFFFFFF0000000000000000FFFFFFFF", 16),
        gx=int("AA87CA22BE8B05378EB1C71EF320AD746E1D3B628BA79B9859F741E082542A38"
               "5502F25DBF55296C3A545E3872760AB7", 16),
        gy=int("3617DE4A96262C6F5D9E98BF9292DC29F8F41DBD289A147CE9DA3113B5F0B8C0"
               "0A60B1CE1D7E819D7A431D7C90EA0E5F", 16))),
    "1.3.132.0.35": ("P-521", dict(
        p=(1 << 521) - 1,
        gx=int("00C6858E06B70404E9CD9E3ECB662395B4429C648139053FB521F828AF606B4D"
               "3DBAA14B5E77EFE75928FE1DC127A2FFA8DE3348B3C1856A429BF97E7E31C2E5"
               "BD66", 16),
        gy=int("011839296A789A3BC0045C8A5FB42C7D1BD998F54449579B446817AFBD17273E"
               "662C97EE72995EF42640C550B9013FAD0761353C7086A272C24088BE94769FD1"
               "6650", 16))),
}


def _ec_add(P, Q, p):
    """Affine Punktaddition für a = -3 (None = Punkt im Unendlichen)."""
    if P is None:
        return Q
    if Q is None:
        return P
    x1, y1 = P
    x2, y2 = Q
    if x1 == x2:
        if (y1 + y2) % p == 0:
            return None
        lam = (3 * x1 * x1 - 3) * pow(2 * y1, -1, p) % p
    else:
        lam = (y2 - y1) * pow(x2 - x1, -1, p) % p
    x3 = (lam * lam - x1 - x2) % p
    return x3, (lam * (x1 - x3) - y1) % p


_TABELLEN: dict[int, dict[int, tuple[int, int]]] = {}


def kleiner_ec_skalar(kurve, x, y, grenze=MAX_KLEINER_SKALAR):
    """Liefert k, falls (x, y) == ±k*G mit 1 <= k < grenze, sonst None.

    Die Vielfachen von G werden pro Kurve einmal berechnet und gecacht.
    """
    p = kurve["p"]
    tabelle = _TABELLEN.get(p)
    if tabelle is None:
        tabelle, G, Q = {}, (kurve["gx"], kurve["gy"]), None
        for k in range(1, grenze):
            Q = _ec_add(Q, G, p)
            tabelle[Q[0]] = (k, Q[1])
        _TABELLEN[p] = tabelle
    treffer = tabelle.get(x)
    if treffer is None:
        return None
    k, ty = treffer
    return k if ty == y else -k  # -k*G ist ebenso trivial (n - k)


# --------------------------------------------------------------------------
# Minimaler DER-Parser
# --------------------------------------------------------------------------
def der_lese(data: bytes, pos: int = 0):
    """Gibt (tag, inhalt_start, inhalt_ende) zurück."""
    tag = data[pos]
    pos += 1
    laenge = data[pos]
    pos += 1
    if laenge & 0x80:
        n = laenge & 0x7F
        laenge = int.from_bytes(data[pos:pos + n], "big")
        pos += n
    return tag, pos, pos + laenge


def der_kinder(data: bytes, start: int, ende: int):
    kinder = []
    pos = start
    while pos < ende:
        tag, s, e = der_lese(data, pos)
        kinder.append((tag, pos, s, e))  # pos = Beginn inkl. Header
        pos = e
    return kinder


def oid_text(b: bytes) -> str:
    teile = [b[0] // 40, b[0] % 40]
    wert = 0
    for byte in b[1:]:
        wert = (wert << 7) | (byte & 0x7F)
        if not byte & 0x80:
            teile.append(wert)
            wert = 0
    return ".".join(map(str, teile))


def name_attribute(data: bytes, s: int, e: int) -> dict:
    attrs = {}
    for _, _, ss, se in der_kinder(data, s, e):          # SET
        for _, _, as_, ae in der_kinder(data, ss, se):   # SEQUENCE
            (_, _, os_, oe), (vt, _, vs, ve) = der_kinder(data, as_, ae)[:2]
            oid = oid_text(data[os_:oe])
            roh = data[vs:ve]
            try:
                wert = roh.decode("utf-16-be") if vt == 0x1E else roh.decode("utf-8")
            except UnicodeDecodeError:
                wert = roh.decode("latin-1")
            attrs.setdefault(oid, wert)
    return attrs


def zertifikat_analysieren(der: bytes) -> dict:
    _, cs, ce = der_lese(der, 0)
    tbs_tag, _, ts, te = der_kinder(der, cs, ce)[0]
    felder = der_kinder(der, ts, te)
    if felder[0][0] == 0xA0:  # [0] version
        felder = felder[1:]
    # serial, sigAlg, issuer, validity, subject, spki
    _, _, ss, se = felder[4]
    subjekt = name_attribute(der, ss, se)
    _, spki_pos, spki_s, spki_e = felder[5]
    spki_der = der[spki_pos:spki_e]
    (_, _, alg_s, alg_e), (_, _, bit_s, bit_e) = der_kinder(der, spki_s, spki_e)
    alg_teile = der_kinder(der, alg_s, alg_e)
    alg_oid = oid_text(der[alg_teile[0][2]:alg_teile[0][3]])
    param_oid = None
    if len(alg_teile) > 1 and alg_teile[1][0] == 0x06:
        param_oid = oid_text(der[alg_teile[1][2]:alg_teile[1][3]])
    schluessel = der[bit_s + 1:bit_e]  # erstes Byte = ungenutzte Bits
    return dict(
        cn=subjekt.get("2.5.4.3", ""),
        o=subjekt.get("2.5.4.10", ""),
        ou=subjekt.get("2.5.4.11", ""),
        alg=alg_oid,
        param=param_oid,
        key=schluessel,
        spki_sha256=hashlib.sha256(spki_der).hexdigest().upper(),
        fp_sha256=hashlib.sha256(der).hexdigest().upper(),
    )


# --------------------------------------------------------------------------
# RSA-Prüfungen
# --------------------------------------------------------------------------
_KLEINE_PRIMZAHLEN = [n for n in range(3, 20000, 2)
                      if all(n % d for d in range(3, int(n ** 0.5) + 1, 2))]
_PRIMPRODUKT = math.prod([2] + _KLEINE_PRIMZAHLEN)


def rsa_befunde(key: bytes) -> tuple[int, list[str]]:
    _, s, e = der_lese(key, 0)
    (_, _, ns, ne), (_, _, es, ee) = der_kinder(key, s, e)[:2]
    n = int.from_bytes(key[ns:ne], "big")
    exp = int.from_bytes(key[es:ee], "big")
    bits = n.bit_length()
    befunde = []
    if bits < MIN_RSA_BITS:
        befunde.append(f"RSA-Modul nur {bits} Bit (< {MIN_RSA_BITS})")
    if exp < 3 or exp % 2 == 0:
        befunde.append(f"ungültiger RSA-Exponent e={exp}")
    g = math.gcd(n, _PRIMPRODUKT)
    if g != 1:
        befunde.append(f"RSA-Modul hat kleinen Primfaktor {g}")
    a = math.isqrt(n)
    if a * a < n:
        a += 1
    for _ in range(2000):  # Fermat: nahe beieinanderliegende Faktoren
        b2 = a * a - n
        b = math.isqrt(b2)
        if b * b == b2:
            befunde.append("RSA-Modul per Fermat faktorisierbar (Primfaktoren zu nahe)")
            break
        a += 1
    return bits, befunde


# --------------------------------------------------------------------------
# Einlesen
# --------------------------------------------------------------------------
PEM_RE = re.compile(rb"-----BEGIN CERTIFICATE-----(.+?)-----END CERTIFICATE-----", re.S)


def pem_dateien(pfade):
    for pfad in pfade:
        if os.path.isdir(pfad):
            for name in sorted(os.listdir(pfad)):
                voll = os.path.join(pfad, name)
                if os.path.isfile(voll) and name.endswith((".pem", ".crt", ".0", ".1")):
                    yield voll
                elif os.path.isfile(voll) and re.fullmatch(r"[0-9a-f]{8}\.\d+", name):
                    yield voll
        elif os.path.isfile(pfad):
            yield pfad
        else:
            raise FileNotFoundError(pfad)


def main(argv) -> int:
    strict_aaa = "--strict-aaa" in argv
    pfade = [a for a in argv if not a.startswith("--")]
    if not pfade:
        print(__doc__)
        return 2
    gesehen = set()
    fehler, warnungen = [], []
    statistik = {"RSA": {}, "EC": {}, "andere": 0}
    try:
        dateien = list(pem_dateien(pfade))
    except FileNotFoundError as exc:
        print(f"FEHLER: Pfad nicht gefunden: {exc}")
        return 2
    for datei in dateien:
        with open(datei, "rb") as fh:
            inhalt = fh.read()
        for m in PEM_RE.finditer(inhalt):
            der = base64.b64decode(b"".join(m.group(1).split()))
            fp = hashlib.sha256(der).hexdigest()
            if fp in gesehen:
                continue
            gesehen.add(fp)
            try:
                z = zertifikat_analysieren(der)
            except Exception as exc:  # defekte Einträge melden, nicht abbrechen
                fehler.append(f"{datei}: Zertifikat nicht lesbar ({exc})")
                continue
            name = z["cn"] or z["ou"] or z["o"] or "?"
            ort = f"{name} [{os.path.basename(datei)}]"
            if z["spki_sha256"] in KOMPROMITTIERTE_SPKI_SHA256:
                fehler.append(f"{ort}: kompromittierter eMudhra-Schlüssel "
                              f"({KOMPROMITTIERTE_SPKI_SHA256[z['spki_sha256']]})")
            if z["cn"] in VERBOTENE_CN:
                fehler.append(f"{ort}: vom eMudhra-Vorfall betroffene CA (SHA-256 {z['fp_sha256']})")
            if z["cn"] == AAA_CN:
                text = (f"{ort}: 'AAA Certificate Services' (Sectigo) vorhanden - "
                        "Cross-Signs der eMudhra-CAs hingen daran; Debian/Ubuntu "
                        "haben die Root entfernt")
                (fehler if strict_aaa else warnungen).append(text)
            if z["alg"] == "1.2.840.113549.1.1.1":
                bits, bef = rsa_befunde(z["key"])
                statistik["RSA"][bits] = statistik["RSA"].get(bits, 0) + 1
                fehler += [f"{ort}: {b}" for b in bef]
            elif z["alg"] == "1.2.840.10045.2.1":
                kurve = KURVEN.get(z["param"])
                kname = kurve[0] if kurve else f"unbekannt ({z['param']})"
                statistik["EC"][kname] = statistik["EC"].get(kname, 0) + 1
                if not kurve:
                    fehler.append(f"{ort}: unbekannte/unsichere EC-Kurve {z['param']}")
                    continue
                key = z["key"]
                if key[0] != 0x04:
                    warnungen.append(f"{ort}: komprimierter EC-Punkt, Skalarprüfung übersprungen")
                    continue
                laenge = (len(key) - 1) // 2
                x = int.from_bytes(key[1:1 + laenge], "big")
                y = int.from_bytes(key[1 + laenge:], "big")
                k = kleiner_ec_skalar(kurve[1], x, y)
                if k is not None:
                    fehler.append(f"{ort}: EC-Schlüssel ({kname}) trivial, "
                                  f"privater Schlüssel = {k}")
            else:
                statistik["andere"] += 1
                warnungen.append(f"{ort}: anderer Schlüsseltyp {z['alg']}")

    print(f"Geprüft: {len(gesehen)} eindeutige Zertifikate aus {len(dateien)} Datei(en)")
    print("  RSA nach Modulgrösse: " +
          ", ".join(f"{b} Bit: {n}" for b, n in sorted(statistik["RSA"].items())))
    print("  EC nach Kurve: " +
          ", ".join(f"{k}: {n}" for k, n in sorted(statistik["EC"].items())))
    for w in warnungen:
        print(f"WARNUNG: {w}")
    for f in fehler:
        print(f"BEFUND:  {f}")
    if not gesehen:
        print("FEHLER: keine Zertifikate gefunden")
        return 2
    print("ERGEBNIS: " + ("NICHT OK" if fehler else "OK"))
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
