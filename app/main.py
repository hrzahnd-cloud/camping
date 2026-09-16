"""
Campingverwaltung Aeschi – FastAPI-Hauptanwendung.

Start (lokal, Entwicklung):
    uvicorn app.main:app --reload

Produktiver Betrieb (z.B. hinter Reverse Proxy) liegt gemäss Absprache
bei den Infrastruktur-Fachpersonen (Hosting, Zugriffssteuerung, 2FA).
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from app.config import get_settings
from app.routers import artikel, buchungen, gaeste, rechnungen, reservationsanfragen, auswertungen

settings = get_settings()

app = FastAPI(
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


@app.get("/health", tags=["System"])
def health_check():
    """Einfacher Health-Check für Monitoring/Hosting."""
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment}


@app.get("/metrics", tags=["System"])
def metrics() -> PlainTextResponse:
    """Prometheus-kompatibler Health-Check für das Atoll-Deployment."""
    body = "# HELP up Ob die Anwendung erreichbar ist.\n# TYPE up gauge\nup 1\n"
    return PlainTextResponse(body, media_type="text/plain; version=0.0.4; charset=utf-8")
