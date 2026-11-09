"""
Unverbindlicher Preis pro Nacht für die Bestätigungsmail (Platzhalter {{preisProNacht}}).

So vom Betrieb gewünscht (November 2026): bei einer vollständigen Anfrage der
Preis pro Nacht aus Erwachsenen und Kindern (Kleinkinder gratis), Zelt/
Wohnwagen/Camper, Umweltabgabe sowie Kurtaxe und Beherbergungsabgabe;
Zwärgli und Spycher pro Nacht für 2 Personen (weitere Personen zum
Personenpreis), dazu die Taxen. Ohne MWST-Angabe. Fahrzeuge sind nicht
enthalten (bei der Anfrage unbekannt).

Liegen die Nächte in verschiedenen Saisons, steht je Saison eine Zeile.
Gerechnet wird mit den Preisen aus «Artikel & Preise». Ist das Modul aus,
entfällt die Zeile still; fehlt für eine Nacht ein Preis (ausserhalb der
Saison), bleibt sie leer und es gibt eine Warnung.
"""
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.artikel import Taxensatz
from app.models.reservation import Reservationsanfrage
from app.services.preise import UNTERKUNFT_PERSONEN_INKL, Preiskontext
from app.services.taxen import _satz_fuer

STELLPLATZ_CODE = {"zeltwiese": "ZELT", "wohnwagen": "WOHNWAGEN", "camper": "CAMPER", "zwaergli": "ZWAERGLI", "spycher": "SPYCHER"}
MIT_UMWELTABGABE = ("zeltwiese", "wohnwagen", "camper")
UNTERKUNFT = ("zwaergli", "spycher")

T = {
    "de": {"titel": "Unverbindlicher Preis pro Nacht", "nacht": ("Nacht", "Nächte"), "e": ("Erwachsene/r", "Erwachsene"),
           "k": ("Kind", "Kinder"), "kk": ("Kleinkind gratis", "Kleinkinder gratis"), "je": "à", "umwelt": "Umweltabgabe",
           "taxen": "Kurtaxe und Beherbergungsabgabe", "personen2": "für 2 Personen", "weitere": ("weitere Person", "weitere Personen"),
           "saison": {"vorsaison": "Vorsaison", "hauptsaison": "Hauptsaison", "nachsaison": "Nachsaison"},
           "typ": {"zeltwiese": "Zelt", "wohnwagen": "Wohnwagen", "camper": "Camper", "zwaergli": "Zwärgli", "spycher": "Spycher"}},
    "fr": {"titel": "Prix indicatif par nuit", "nacht": ("nuit", "nuits"), "e": ("adulte", "adultes"),
           "k": ("enfant", "enfants"), "kk": ("petit enfant gratuit", "petits enfants gratuits"), "je": "à", "umwelt": "taxe environnementale",
           "taxen": "taxe de séjour et taxe d’hébergement", "personen2": "pour 2 personnes", "weitere": ("personne supplémentaire", "personnes supplémentaires"),
           "saison": {"vorsaison": "avant-saison", "hauptsaison": "haute saison", "nachsaison": "arrière-saison"},
           "typ": {"zeltwiese": "tente", "wohnwagen": "caravane", "camper": "camping-car", "zwaergli": "Zwärgli", "spycher": "Spycher"}},
    "it": {"titel": "Prezzo indicativo per notte", "nacht": ("notte", "notti"), "e": ("adulto", "adulti"),
           "k": ("bambino", "bambini"), "kk": ("bimbo piccolo gratis", "bimbi piccoli gratis"), "je": "a", "umwelt": "tassa ambientale",
           "taxen": "tassa di soggiorno e tassa d’alloggio", "personen2": "per 2 persone", "weitere": ("persona in più", "persone in più"),
           "saison": {"vorsaison": "bassa stagione", "hauptsaison": "alta stagione", "nachsaison": "bassa stagione"},
           "typ": {"zeltwiese": "tenda", "wohnwagen": "roulotte", "camper": "camper", "zwaergli": "Zwärgli", "spycher": "Spycher"}},
    "en": {"titel": "Indicative price per night", "nacht": ("night", "nights"), "e": ("adult", "adults"),
           "k": ("child", "children"), "kk": ("infant free", "infants free"), "je": "at", "umwelt": "environmental fee",
           "taxen": "tourist tax and accommodation levy", "personen2": "for 2 people", "weitere": ("additional person", "additional people"),
           "saison": {"vorsaison": "pre-season", "hauptsaison": "high season", "nachsaison": "post-season"},
           "typ": {"zeltwiese": "tent", "wohnwagen": "caravan", "camper": "camper van", "zwaergli": "Zwärgli", "spycher": "Spycher"}},
}


@dataclass
class Abschnitt:
    saison: str | None
    naechte: int
    posten: tuple
    """((schlüssel, anzahl, einzelpreis), …) – gleich für alle Nächte des Abschnitts."""
    total: Decimal = field(default=Decimal("0.00"))


def berechnen(db: Session, a: Reservationsanfrage) -> tuple[list[Abschnitt], str | None]:
    """Abschnitte gleicher Preise je Nacht; bei fehlendem Preis ([], Grund)."""
    if not (a.gewuenscht_von and a.gewuenscht_bis and a.stellplatz_typ in STELLPLATZ_CODE) or a.gewuenscht_bis <= a.gewuenscht_von:
        return [], "Zeitraum oder Stellplatz fehlt"
    ctx = Preiskontext(db)
    saetze = list(db.execute(select(Taxensatz)).scalars())
    e, k, kk = a.anzahl_erwachsene or 0, a.anzahl_kinder or 0, a.anzahl_kleinkinder or 0
    abschnitte: list[Abschnitt] = []
    tag = a.gewuenscht_von
    while tag < a.gewuenscht_bis:
        def p(code):
            wert = ctx.preis(code, tag)
            if wert is None:
                raise LookupError(code)
            return wert
        try:
            posten = []
            if a.stellplatz_typ in UNTERKUNFT:
                posten.append(("unterkunft", 1, p(STELLPLATZ_CODE[a.stellplatz_typ])))
                frei = UNTERKUNFT_PERSONEN_INKL
                e_zahl, k_zahl = max(0, e - frei), max(0, k - max(0, frei - e))
            else:
                posten.append(("stellplatz", 1, p(STELLPLATZ_CODE[a.stellplatz_typ])))
                e_zahl, k_zahl = e, k
            if e_zahl:
                posten.append(("e", e_zahl, p("ERWACHSENE")))
            if k_zahl:
                posten.append(("k", k_zahl, p("KINDER")))
            if a.stellplatz_typ in MIT_UMWELTABGABE:
                posten.append(("umwelt", 1, p("UMWELTABGABE")))
            taxe = sum((Decimal(str(s.betrag_pro_nacht)) for typ in ("kurtaxe_gemeinde", "beherbergungsabgabe_kanton")
                        if (s := _satz_fuer(saetze, typ, tag, 30)) is not None), Decimal("0.00"))
            if e and taxe:
                posten.append(("taxen", e, taxe))
            if kk:
                posten.append(("kk", kk, Decimal("0.00")))
        except LookupError:
            return [], f"Kein Preis für den {tag.day}.{tag.month}.{tag.year} hinterlegt (ausserhalb der Saison?)"
        saison = ctx.saison_am(tag)
        schluessel = (saison.typ if saison else None, tuple(posten))
        if abschnitte and (abschnitte[-1].saison, abschnitte[-1].posten) == schluessel:
            abschnitte[-1].naechte += 1
        else:
            abschnitte.append(Abschnitt(saison=schluessel[0], naechte=1, posten=schluessel[1],
                                        total=sum((n * preis for _, n, preis in posten), Decimal("0.00"))))
        tag += timedelta(days=1)
    return abschnitte, None


def _chf(x: Decimal) -> str:
    return f"CHF {x:.2f}"


def _wort(paar, n):
    return paar[0] if n == 1 else paar[1]


def text(db: Session, a: Reservationsanfrage, sprache: str) -> tuple[str, str | None]:
    """(Text für {{preisProNacht}}, Warnung oder None)."""
    abschnitte, grund = berechnen(db, a)
    if not abschnitte:
        return "", f"Unverbindlicher Preis nicht eingesetzt: {grund}."
    t = T.get(sprache, T["de"])
    zeilen = []
    for ab in abschnitte:
        teile = []
        for schluessel, n, preis in ab.posten:
            if schluessel == "stellplatz":
                teile.append(f"{t['typ'][a.stellplatz_typ]} {_chf(preis)}")
            elif schluessel == "unterkunft":
                teile.append(f"{t['typ'][a.stellplatz_typ]} {t['personen2']} {_chf(preis)}")
            elif schluessel == "e":
                wort = _wort(t["weitere"], n) if a.stellplatz_typ in UNTERKUNFT else _wort(t["e"], n)
                teile.append(f"{n} {wort} {t['je']} {_chf(preis)}")
            elif schluessel == "k":
                teile.append(f"{n} {_wort(t['k'], n)} {t['je']} {_chf(preis)}")
            elif schluessel == "umwelt":
                teile.append(f"{t['umwelt']} {_chf(preis)}")
            elif schluessel == "taxen":
                teile.append(f"{t['taxen']} {_chf(preis * n)}")
            elif schluessel == "kk":
                teile.append(f"{n} {_wort(t['kk'], n)}")
        saison = t["saison"].get(ab.saison, "")
        zusatz = f" ({saison}, {ab.naechte} {_wort(t['nacht'], ab.naechte)})" if len(abschnitte) > 1 else (f" ({saison})" if saison else "")
        zeilen.append(f"{t['titel']}{zusatz}: {_chf(ab.total)}\n" + ", ".join(teile))
    return "\n\n".join(zeilen), None



def fuer_vorlage(db: Session, a: Reservationsanfrage, sprache: str, vorlagentext: str) -> tuple[str, str | None]:
    """Nur rechnen, wenn die Vorlage den Platzhalter enthält und das Modul «Artikel & Preise» eingeschaltet ist."""
    from app.services.module import modul_aktiv
    if "preisProNacht" not in vorlagentext:
        return "", None
    if not modul_aktiv(db, "artikel"):
        return "", None  # ohne Preis-Modul entfällt die Zeile still (Reservationen laufen auch ohne Modul)
    return text(db, a, sprache)
