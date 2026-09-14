"""
Zentrale Registrierung aller ORM-Modelle.

Wichtig: ALLE Modell-Module müssen hier importiert werden, damit
SQLAlchemy String-Relationships (z.B. Mapped["Buchung"]) zur Laufzeit
auflösen kann und Alembic beim Autogenerate alle Tabellen sieht.
"""
from app.database import Base  # noqa: F401

from app.models.campingplatz import Campingplatz, Stellplatz  # noqa: F401
from app.models.artikel import Mwstsatz, Saison, Artikel, ArtikelPreis, Taxensatz  # noqa: F401
from app.models.buchung import Gast, Buchung, Aufenthalt  # noqa: F401
from app.models.reservation import (  # noqa: F401
    Reservationsanfrage,
    Zahlung,
    Zahlungsanbieterkonfiguration,
)
from app.models.kommunikation import EmailVorlage, EmailVersand  # noqa: F401
from app.models.newsletter import (  # noqa: F401
    MailchimpKonfiguration,
    NewsletterAbo,
    NewsletterKampagne,
    NewsletterVersand,
)
from app.models.rechnung import (  # noqa: F401
    Rechnungsnummernzaehler,
    Rechnung,
    Rechnungsposition,
)
from app.models.meldungen import (  # noqa: F401
    FeratelKonfiguration,
    FeratelMeldung,
    HestaMeldung,
    HestaMeldungPosition,
)

__all__ = [
    "Base",
    "Campingplatz",
    "Stellplatz",
    "Mwstsatz",
    "Saison",
    "Artikel",
    "ArtikelPreis",
    "Taxensatz",
    "Gast",
    "Buchung",
    "Aufenthalt",
    "Reservationsanfrage",
    "Zahlung",
    "Zahlungsanbieterkonfiguration",
    "EmailVorlage",
    "EmailVersand",
    "MailchimpKonfiguration",
    "NewsletterAbo",
    "NewsletterKampagne",
    "NewsletterVersand",
    "Rechnungsnummernzaehler",
    "Rechnung",
    "Rechnungsposition",
    "FeratelKonfiguration",
    "FeratelMeldung",
    "HestaMeldung",
    "HestaMeldungPosition",
]
