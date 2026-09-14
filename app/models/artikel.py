"""
Preis- und Steuermodell: Saison, Mwstsatz, Artikel, ArtikelPreis, Taxensatz.

Zentrales Prinzip (siehe Konzeptdokument Abschnitt 9): der MWST-Satz wird
NICHT als Zahl am Artikel gespeichert, sondern über `mwstsatz_id` referenziert.
Eine Satzänderung erfolgt durch einen neuen `Mwstsatz`-Datensatz mit neuem
Gültigkeitsbeginn – der alte bleibt historisch erhalten.
"""
import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import GUID, IDMixin, TimestampMixin


class Mwstsatz(Base, IDMixin, TimestampMixin):
    """
    Zentral verwalteter MWST-Satz, historisiert nach Gültigkeitsdatum.

    code: BEHERBERGUNG | NORMAL | REDUZIERT | AUSGENOMMEN
    """
    __tablename__ = "mwstsatz"

    code: Mapped[str] = mapped_column(String(30), index=True)
    bezeichnung: Mapped[str] = mapped_column(String(100))
    satz_prozent: Mapped[float] = mapped_column(Numeric(5, 2))
    gueltig_ab: Mapped[date] = mapped_column(Date)
    gueltig_bis: Mapped[date | None] = mapped_column(Date)
    """NULL = aktuell gültig / noch offen."""

    artikel: Mapped[list["Artikel"]] = relationship(back_populates="mwstsatz")


class Saison(Base, IDMixin, TimestampMixin):
    """Zeitraum mit eigener Preisgültigkeit (Hauptsaison, Vor-/Nachsaison)."""
    __tablename__ = "saison"

    bezeichnung: Mapped[str] = mapped_column(String(100))
    gueltig_ab: Mapped[date] = mapped_column(Date)
    gueltig_bis: Mapped[date] = mapped_column(Date)

    artikelpreise: Mapped[list["ArtikelPreis"]] = relationship(back_populates="saison")


class Artikel(Base, IDMixin, TimestampMixin):
    """Zentraler Artikelstamm: Verkaufs-/Leistungsposition des Campingplatzes."""
    __tablename__ = "artikel"

    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    bezeichnung: Mapped[str] = mapped_column(String(150))
    kategorie: Mapped[str] = mapped_column(String(50))
    """person | stellplatz | unterkunftseinheit | zusatzleistung | taxe"""
    einheit: Mapped[str] = mapped_column(String(30), default="pro_nacht")
    """pro_nacht | pro_person | pro_tag | stueck"""
    mwstsatz_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("mwstsatz.id"))
    aktiv: Mapped[bool] = mapped_column(default=True)

    mwstsatz: Mapped["Mwstsatz"] = relationship(back_populates="artikel")
    preise: Mapped[list["ArtikelPreis"]] = relationship(back_populates="artikel")


class ArtikelPreis(Base, IDMixin, TimestampMixin):
    """Preis eines Artikels für eine bestimmte Saison (oder saisonunabhängig)."""
    __tablename__ = "artikel_preis"

    artikel_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("artikel.id"))
    saison_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("saison.id"))
    """NULL = saisonunabhängig gültig (z.B. Kurtaxe, Strom, Umweltabgabe)."""
    preis: Mapped[float] = mapped_column(Numeric(8, 2))

    artikel: Mapped["Artikel"] = relationship(back_populates="preise")
    saison: Mapped["Saison | None"] = relationship(back_populates="artikelpreise")


class Taxensatz(Base, IDMixin, TimestampMixin):
    """
    Konfigurierbare Abgabensätze (Kurtaxe Gemeinde / kantonale
    Beherbergungsabgabe) nach Gültigkeitszeitraum und Altersgruppe.
    Bewusst getrennt vom Artikel-/MWST-Modell, da es sich um
    durchlaufende Posten ohne MWST handelt (siehe Konzept Abschnitt 9.2).
    """
    __tablename__ = "taxensatz"

    typ: Mapped[str] = mapped_column(String(50))
    """kurtaxe_gemeinde | beherbergungsabgabe_kanton"""
    gueltig_ab: Mapped[date] = mapped_column(Date)
    gueltig_bis: Mapped[date | None] = mapped_column(Date)
    altersgruppe_von: Mapped[int | None] = mapped_column(Integer)
    altersgruppe_bis: Mapped[int | None] = mapped_column(Integer)
    betrag_pro_nacht: Mapped[float] = mapped_column(Numeric(6, 2))
    gemeinde_oder_kanton: Mapped[str] = mapped_column(String(50))
