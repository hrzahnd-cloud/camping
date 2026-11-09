"""MWST: Strom, Wasser, Umweltabgabe, Auto und Motorrad zum Sondersatz Beherbergung

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-09 18:00:00

Vom Betrieb bestätigt (November 2026): Strom- und Wasserversorgung, Abwasser-
und Kehrichtentsorgung (Umweltabgabe) sowie Auto/Parking der Übernachtungsgäste
sind Nebenleistungen der Beherbergung und unterliegen wie die Stellplatzmiete
dem Sondersatz (3.8 %). Bestehende Rechnungen bleiben unverändert (der Satz ist
dort als Kopie gespeichert).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0012'
down_revision: Union[str, None] = '0011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CODES = ('STROM', 'UMWELTABGABE', 'WASSERTANK', 'AUTO', 'MOTORRAD')


def _setze(code_mwst: str) -> None:
    con = op.get_bind()
    satz = con.execute(sa.text("SELECT id FROM mwstsatz WHERE code = :c ORDER BY gueltig_ab DESC LIMIT 1"),
                       {"c": code_mwst}).scalar()
    if satz is None:
        return  # leere Datenbank: die Grunddaten setzen die Sätze richtig
    artikel = sa.table('artikel', sa.column('code', sa.String), sa.column('mwstsatz_id'))
    con.execute(artikel.update().where(artikel.c.code.in_(CODES)).values(mwstsatz_id=satz))


def upgrade() -> None:
    _setze('BEHERBERGUNG')


def downgrade() -> None:
    _setze('NORMAL')
