"""
E-Mail-Versand über SMTP (aktuell für die HESTA-Meldung).

Die SMTP-Zugangsdaten sind noch nicht hinterlegt: ohne `smtp_host` wird
nichts versendet, sondern `MailNichtKonfiguriert` ausgelöst.
"""
import smtplib
import ssl
from email.message import EmailMessage

from app.config import Settings


class MailNichtKonfiguriert(Exception):
    """SMTP-Zugangsdaten sind (noch) nicht hinterlegt."""


def smtp_konfiguriert(settings: Settings) -> bool:
    return bool(settings.smtp_host)


def sende_mail(settings: Settings, nachricht: EmailMessage) -> None:
    if not smtp_konfiguriert(settings):
        raise MailNichtKonfiguriert("SMTP_HOST ist nicht gesetzt.")

    kontext = ssl.create_default_context()
    if settings.smtp_port == 465:
        server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=kontext, timeout=30)
    else:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30)
    with server:
        if settings.smtp_port != 465:
            server.starttls(context=kontext)
        if settings.smtp_user and settings.smtp_password:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(nachricht)
