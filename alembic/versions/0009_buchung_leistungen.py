"""Leistungen je Aufenthalt (Personen, Stellplatz, Zusatzleistungen mit eigenem Zeitraum)

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-09 16:00:00

Bestehende Aufenthalte erhalten Zeilen aus ihren Personenzahlen und dem
Stellplatz-Typ über den ganzen Aufenthalt (bei Zelt/Wohnwagen/Camper mit
Umweltabgabe pro Stellplatz und Nacht).
"""
import uuid
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.models.common


revision: str = '0009'
down_revision: Union[str, None] = '0008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

STELLPLATZ = ('zeltwiese', 'wohnwagen', 'camper', 'zwaergli', 'spycher')


def upgrade() -> None:
    tabelle = op.create_table(
        'buchung_leistung',
        sa.Column('buchung_id', app.models.common.GUID(), nullable=False),
        sa.Column('art', sa.String(length=30), nullable=False),
        sa.Column('anzahl', sa.Integer(), nullable=False),
        sa.Column('von', sa.Date(), nullable=False),
        sa.Column('bis', sa.Date(), nullable=False),
        sa.Column('kurtaxepflichtig', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('bemerkung', sa.String(length=200), nullable=True),
        sa.Column('id', app.models.common.GUID(), nullable=False),
        sa.Column('erstellt_am', sa.DateTime(timezone=True), nullable=False),
        sa.Column('geaendert_am', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['buchung_id'], ['buchung.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_buchung_leistung_buchung_id', 'buchung_leistung', ['buchung_id'])

    jetzt = datetime.now(timezone.utc)
    zeilen = []
    for b in op.get_bind().execute(sa.text(
            "SELECT id, von, bis, stellplatz_typ, anzahl_erwachsene, anzahl_kinder, anzahl_kleinkinder "
            "FROM buchung WHERE status != 'storniert'")).mappings():
        teile = [('erwachsene', b['anzahl_erwachsene']), ('kinder', b['anzahl_kinder']),
                 ('kleinkinder', b['anzahl_kleinkinder'])]
        if b['stellplatz_typ'] in STELLPLATZ:
            teile.append((b['stellplatz_typ'], 1))
        if b['stellplatz_typ'] in ('zeltwiese', 'wohnwagen', 'camper'):
            teile.append(('umweltabgabe', 1))  # pro Stellplatz und Nacht
        for art, anzahl in teile:
            if anzahl:
                zeilen.append(dict(id=uuid.uuid4(), buchung_id=b['id'], art=art, anzahl=anzahl, von=b['von'],
                                   bis=b['bis'], kurtaxepflichtig=True, bemerkung=None,
                                   erstellt_am=jetzt, geaendert_am=jetzt))
    if zeilen:
        op.bulk_insert(tabelle, zeilen)


def downgrade() -> None:
    op.drop_index('ix_buchung_leistung_buchung_id', table_name='buchung_leistung')
    op.drop_table('buchung_leistung')
