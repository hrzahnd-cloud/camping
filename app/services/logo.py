"""
Logo des Betriebs für die Rechnung. Wird unter Einstellungen hochgeladen und in
der Datenbank gespeichert – nicht im Code (das Repository ist öffentlich).
"""
import base64
import binascii
from io import BytesIO

from PIL import Image
from sqlalchemy.orm import Session

from app.models.einstellungen import AppEinstellung

SCHLUESSEL = "logo"
MAX_BYTES = 2_000_000
MAX_PIXEL = 1200
"""Grössere Bilder werden verkleinert, damit das PDF klein bleibt."""


class LogoFehler(ValueError):
    pass


def lesen(db: Session) -> tuple[bytes, str] | None:
    e = db.get(AppEinstellung, SCHLUESSEL)
    if not e or not e.wert:
        return None
    kopf, _, daten = e.wert.partition(",")
    return base64.b64decode(daten), kopf.removeprefix("data:").removesuffix(";base64")


def speichern(db: Session, data_url: str) -> None:
    kopf, _, daten = (data_url or "").partition(",")
    if not kopf.startswith("data:image/") or ";base64" not in kopf:
        raise LogoFehler("Bitte ein Bild (PNG oder JPG) wählen")
    try:
        roh = base64.b64decode(daten, validate=True)
    except binascii.Error:
        raise LogoFehler("Das Bild ist beschädigt")
    if len(roh) > MAX_BYTES:
        raise LogoFehler("Das Bild ist grösser als 2 MB")
    try:
        bild = Image.open(BytesIO(roh))
        bild.load()
    except Exception:
        raise LogoFehler("Das Bild lässt sich nicht lesen (PNG oder JPG)")
    if bild.format not in ("PNG", "JPEG"):
        raise LogoFehler("Bitte ein PNG- oder JPG-Bild verwenden")
    if max(bild.size) > MAX_PIXEL:
        bild.thumbnail((MAX_PIXEL, MAX_PIXEL))
    puffer = BytesIO()
    if bild.format == "JPEG" or bild.mode not in ("RGBA", "LA", "P"):
        bild.convert("RGB").save(puffer, "JPEG", quality=88)
        typ = "image/jpeg"
    else:
        bild.save(puffer, "PNG", optimize=True)
        typ = "image/png"
    wert = f"data:{typ};base64," + base64.b64encode(puffer.getvalue()).decode()
    e = db.get(AppEinstellung, SCHLUESSEL)
    if e is None:
        db.add(AppEinstellung(schluessel=SCHLUESSEL, wert=wert))
    else:
        e.wert = wert
    db.commit()


def loeschen(db: Session) -> None:
    e = db.get(AppEinstellung, SCHLUESSEL)
    if e is not None:
        db.delete(e)
        db.commit()
