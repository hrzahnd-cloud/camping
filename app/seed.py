"""
Grunddaten für einen frischen Betrieb.

Preise gemäss camping-aeschi.ch/preise-2 (Stand 2026, siehe Konzeptdokument
Abschnitt 9.3). MWST-Satz Beherbergung: aktuell (2024-2027) 3.8% – der im
Gespräch genannte Satz von 3.6% war 2018-2023 gültig; VOR dem produktiven
Einsatz mit Treuhänder/ESTV verifizieren (Konzeptdokument Abschnitt 9.1).

Ausführen mit:  python -m app.seed
"""
from datetime import date
from decimal import Decimal

from app.database import SessionLocal
from app.models import Artikel, ArtikelPreis, Mwstsatz, Saison, Taxensatz


def seed() -> None:
    db = SessionLocal()
    try:
        # --- MWST-Sätze -----------------------------------------------
        mwst_beherbergung = Mwstsatz(
            code="BEHERBERGUNG",
            bezeichnung="Sondersatz Beherbergung",
            satz_prozent=Decimal("3.8"),
            gueltig_ab=date(2024, 1, 1),
            gueltig_bis=None,
        )
        mwst_normal = Mwstsatz(
            code="NORMAL",
            bezeichnung="Normalsatz",
            satz_prozent=Decimal("8.1"),
            gueltig_ab=date(2024, 1, 1),
            gueltig_bis=None,
        )
        mwst_ausgenommen = Mwstsatz(
            code="AUSGENOMMEN",
            bezeichnung="Ausgenommen (durchlaufender Posten)",
            satz_prozent=Decimal("0.0"),
            gueltig_ab=date(2000, 1, 1),
            gueltig_bis=None,
        )
        db.add_all([mwst_beherbergung, mwst_normal, mwst_ausgenommen])
        db.flush()

        # --- Saisons 2026 -----------------------------------------------
        hauptsaison = Saison(
            bezeichnung="Hauptsaison 2026",
            gueltig_ab=date(2026, 7, 1),
            gueltig_bis=date(2026, 8, 30),
        )
        vor_nachsaison = Saison(
            bezeichnung="Vor-/Nachsaison 2026",
            gueltig_ab=date(2026, 5, 1),
            gueltig_bis=date(2026, 9, 30),
        )
        db.add_all([hauptsaison, vor_nachsaison])
        db.flush()

        # --- Artikel + saisonale Preise ----------------------------------
        # (bezeichnung, code, kategorie, einheit, mwstsatz, preis_hauptsaison, preis_vornachsaison)
        artikel_saisonal = [
            ("Erwachsene", "ERWACHSENE", "person", "pro_person_nacht", mwst_beherbergung, "8.00", "7.00"),
            ("Kinder", "KINDER", "person", "pro_person_nacht", mwst_beherbergung, "4.00", "3.40"),
            ("Camper", "CAMPER", "stellplatz", "pro_nacht", mwst_beherbergung, "18.00", "16.00"),
            ("Wohnwagen", "WOHNWAGEN", "stellplatz", "pro_nacht", mwst_beherbergung, "17.00", "15.00"),
            ("Zelt", "ZELT", "stellplatz", "pro_nacht", mwst_beherbergung, "14.00", "12.00"),
            ("Auto", "AUTO", "zusatzleistung", "pro_nacht", mwst_normal, "3.00", "3.00"),
            ("Motorrad", "MOTORRAD", "zusatzleistung", "pro_nacht", mwst_normal, "2.00", "1.70"),
        ]
        for bezeichnung, code, kategorie, einheit, mwstsatz, preis_haupt, preis_vor in artikel_saisonal:
            artikel = Artikel(
                code=code, bezeichnung=bezeichnung, kategorie=kategorie,
                einheit=einheit, mwstsatz_id=mwstsatz.id,
            )
            db.add(artikel)
            db.flush()
            db.add(ArtikelPreis(artikel_id=artikel.id, saison_id=hauptsaison.id, preis=Decimal(preis_haupt)))
            db.add(ArtikelPreis(artikel_id=artikel.id, saison_id=vor_nachsaison.id, preis=Decimal(preis_vor)))

        # Saisonunabhängige Positionen (kein saison_id -> ganzjährig gültig)
        artikel_ganzjaehrig = [
            ("Kleinkinder (2-5 Jahre)", "KLEINKINDER", "person", "pro_person_nacht", mwst_beherbergung, "0.00"),
            ("Elektrische Energie", "STROM", "zusatzleistung", "pro_tag", mwst_normal, "4.00"),
            ("Umweltabgabe", "UMWELTABGABE", "zusatzleistung", "pro_nacht", mwst_normal, "1.00"),
            ("Wassertankfüllung", "WASSERTANK", "zusatzleistung", "stueck", mwst_normal, "5.00"),
            ("Zwärgli (2 Personen/Nacht)", "ZWAERGLI", "unterkunftseinheit", "pro_nacht", mwst_beherbergung, "40.00"),
            ("Spycher (2 Personen/Nacht)", "SPYCHER", "unterkunftseinheit", "pro_nacht", mwst_beherbergung, "60.00"),
        ]
        for bezeichnung, code, kategorie, einheit, mwstsatz, preis in artikel_ganzjaehrig:
            artikel = Artikel(
                code=code, bezeichnung=bezeichnung, kategorie=kategorie,
                einheit=einheit, mwstsatz_id=mwstsatz.id,
            )
            db.add(artikel)
            db.flush()
            db.add(ArtikelPreis(artikel_id=artikel.id, saison_id=None, preis=Decimal(preis)))

        # --- Taxensätze (durchlaufende Posten, kein MWST-Objekt) ---------
        db.add(Taxensatz(
            typ="kurtaxe_gemeinde", gueltig_ab=date(2026, 1, 1), gueltig_bis=None,
            altersgruppe_von=16, altersgruppe_bis=120,
            betrag_pro_nacht=Decimal("3.50"), gemeinde_oder_kanton="Aeschi",
        ))
        db.add(Taxensatz(
            typ="kurtaxe_gemeinde", gueltig_ab=date(2026, 1, 1), gueltig_bis=None,
            altersgruppe_von=0, altersgruppe_bis=15,
            betrag_pro_nacht=Decimal("0.00"), gemeinde_oder_kanton="Aeschi",
        ))
        db.add(Taxensatz(
            typ="beherbergungsabgabe_kanton", gueltig_ab=date(2026, 1, 1), gueltig_bis=None,
            altersgruppe_von=0, altersgruppe_bis=120,
            betrag_pro_nacht=Decimal("1.00"), gemeinde_oder_kanton="Bern",
        ))

        db.commit()
        print("Grunddaten erfolgreich eingespielt.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
