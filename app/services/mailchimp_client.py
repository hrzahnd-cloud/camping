"""
Mailchimp-Anbindung für den Newsletter (Konzeptdokument Abschnitt 11.3/11.4).

STATUS: GERÜST VORHANDEN, NICHT PRODUKTIV.

Die eigentliche API-Kommunikation ist hier als klar abgegrenzte Funktion
vorbereitet, aber nicht aktiviert – Voraussetzung ist ein eingerichtetes
Mailchimp-Konto mit Audience und API-Key (siehe Konzept 11.4, offener
Punkt). Sobald `MailchimpKonfiguration.aktiv = True` gesetzt ist, kann
hier die Mailchimp-API (`mailchimp_marketing`-Paket) angebunden werden.

WICHTIG (rechtlich, siehe Konzept 11.1): `NewsletterAbo` bleibt in jedem
Fall die führende Quelle für die Einwilligung. Diese Funktion synchronisiert
nur, sie erzeugt keine Einwilligung.
"""
from app.models.newsletter import MailchimpKonfiguration, NewsletterAbo


class MailchimpNichtKonfiguriert(Exception):
    """Wird ausgelöst, solange keine gültige MailchimpKonfiguration aktiv ist."""


def synchronisiere_abo(abo: NewsletterAbo, konfiguration: MailchimpKonfiguration) -> None:
    """
    Würde ein NewsletterAbo mit der konfigurierten Mailchimp-Audience
    synchronisieren (hinzufügen/aktualisieren inkl. Sprach-Tag, oder bei
    status='abgemeldet' in Mailchimp als unsubscribed markieren).

    Aktuell nicht produktiv – siehe Moduldocstring.
    """
    if not konfiguration.aktiv:
        raise MailchimpNichtKonfiguriert(
            "Mailchimp-Anbindung ist noch nicht konfiguriert/aktiviert. "
            "Voraussetzung: Mailchimp-Konto, Audience und API-Key "
            "gemäss Konzeptdokument Abschnitt 11.4 einrichten."
        )
    raise NotImplementedError(
        "Mailchimp-API-Anbindung (Paket 'mailchimp_marketing') ist noch "
        "zu implementieren, sobald die Konfiguration vorliegt."
    )


def verarbeite_abmeldung_webhook(payload: dict) -> str:
    """
    Würde einen Mailchimp-Unsubscribe-Webhook verarbeiten und das lokale
    NewsletterAbo entsprechend auf status='abgemeldet' setzen.

    Aktuell nicht produktiv – siehe Moduldocstring.
    """
    raise NotImplementedError(
        "Webhook-Verarbeitung ist noch zu implementieren, sobald die "
        "Mailchimp-Anbindung aktiv ist."
    )
