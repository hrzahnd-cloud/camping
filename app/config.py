"""
Zentrale Konfiguration der Anwendung.

Alle Werte werden aus Umgebungsvariablen gelesen (siehe .env.example).
Hosting/Secrets-Verwaltung liegt bewusst ausserhalb dieses Codes –
das übernehmen gemäss Absprache die Fachpersonen für Infrastruktur.
"""
from functools import lru_cache
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Datenbank
    # DATABASE_URL hat Vorrang, falls gesetzt (z.B. lokale Entwicklung).
    # Ohne DATABASE_URL wird die Verbindung aus DB_HOST/DB_PORT/DB_NAME/
    # DB_USER/DB_PASSWORD zusammengesetzt (so stellt Atoll die Werte für
    # die von ihm verwaltete Datenbank bereit).
    database_url: str | None = None
    db_host: str = "db"
    db_port: int = 5432
    db_name: str = "campingverwaltung"
    db_user: str = "camping_user"
    db_password: str = ""

    # Allgemein
    app_name: str = "Campingverwaltung Aeschi"
    environment: str = "development"  # development | staging | production

    # E-Mail-Versand (Reservationsantworten, Rechnungen)
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_absender: str = "info@camping-aeschi.ch"

    # Mailchimp (Newsletter) – bis zur Aktivierung leer/inaktiv
    mailchimp_api_key: str | None = None
    mailchimp_server_prefix: str | None = None
    mailchimp_audience_id: str | None = None

    # Feratel Deskline (Kurtaxe/Beherbergungsabgabe-Meldung) – bis zur
    # PMS-Partner-Freischaltung durch Thun-Thunersee Tourismus nicht nutzbar
    feratel_endpoint_url: str | None = None
    feratel_gemeinde_nummer: str | None = None
    feratel_firmen_nummer: str | None = None
    feratel_benutzer: str | None = None
    feratel_passwort: str | None = None

    @model_validator(mode="after")
    def _fallback_database_url(self) -> "Settings":
        if not self.database_url:
            self.database_url = (
                f"postgresql+psycopg://{self.db_user}:{self.db_password}"
                f"@{self.db_host}:{self.db_port}/{self.db_name}"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
