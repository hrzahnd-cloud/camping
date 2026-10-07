"""
Campingverwaltung Aeschi – FastAPI-Hauptanwendung.

Start (lokal, Entwicklung):
    uvicorn app.main:app --reload

Produktiver Betrieb (z.B. hinter Reverse Proxy) liegt gemäss Absprache
bei den Infrastruktur-Fachpersonen (Hosting, Zugriffssteuerung, 2FA).
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from app.config import get_settings
from app.database import SessionLocal
from app.routers import artikel, buchungen, feratel, gaeste, hesta, rechnungen, reservationsanfragen, auswertungen
from app.services.mail_import import imap_konfiguriert, importiere_aus_postfach

settings = get_settings()
log = logging.getLogger("app.mail_import")


def _postfach_einmal_abfragen() -> None:
    db = SessionLocal()
    try:
        ergebnis = importiere_aus_postfach(db, settings)
        if ergebnis.neu or ergebnis.fehler:
            log.info("Mail-Import: %s neu, %s Fehler", ergebnis.neu, len(ergebnis.fehler))
    except Exception:
        log.exception("Mail-Import fehlgeschlagen")
    finally:
        db.close()


async def _postfach_schleife() -> None:
    while True:
        await asyncio.to_thread(_postfach_einmal_abfragen)
        await asyncio.sleep(settings.mail_import_intervall_sekunden)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Startet die automatische Postfach-Abfrage nur, wenn IMAP konfiguriert ist."""
    aufgabe = None
    if imap_konfiguriert(settings) and settings.mail_import_intervall_sekunden > 0:
        aufgabe = asyncio.create_task(_postfach_schleife())
    yield
    if aufgabe:
        aufgabe.cancel()


app = FastAPI(
    lifespan=lifespan,
    title=settings.app_name,
    description=(
        "Backend der Campingverwaltungssoftware. Datenmodell und Fachlogik "
        "gemäss dem gemeinsam erarbeiteten Konzeptdokument. Einige Module "
        "(Feratel-Meldung, Mailchimp-Sync, Kreditkarten-Zahlung) sind als "
        "Platzhalter angelegt, siehe jeweilige Services für Details."
    ),
    version="0.1.0",
)

# CORS: hier sehr offen für die Entwicklung; für Produktion durch die
# Infrastruktur-Fachpersonen auf die tatsächliche Frontend-Domain einschränken.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(gaeste.router)
app.include_router(buchungen.router)
app.include_router(reservationsanfragen.router)
app.include_router(artikel.router)
app.include_router(rechnungen.router)
app.include_router(auswertungen.router)
app.include_router(hesta.router)
app.include_router(feratel.router)


@app.get("/health", tags=["System"])
def health_check():
    """Einfacher Health-Check für Monitoring/Hosting."""
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment}


@app.get("/metrics", tags=["System"])
def metrics() -> PlainTextResponse:
    """Prometheus-kompatibler Health-Check für das Atoll-Deployment."""
    body = (
        "# HELP up Ob die Anwendung erreichbar ist.\n# TYPE up gauge\nup 1\n"
        "# HELP app_info Versionsinformation der Anwendung.\n# TYPE app_info gauge\n"
        'app_info{version="0.1.0"} 1\n'
    )
    return PlainTextResponse(body, media_type="text/plain; version=0.0.4; charset=utf-8")
