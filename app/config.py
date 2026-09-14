"""
Zentrale Konfiguration der Anwendung.

Alle Werte werden aus Umgebungsvariablen gelesen (siehe .env.example).
Hosting/Secrets-Verwaltung liegt bewusst ausserhalb dieses Codes –
das übernehmen gemäss Absprache die Fachpersonen für Infrastruktur.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Datenbank
    database_url: str = "postgresql+psycopg://user:password@localhost:5432/camping"

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
