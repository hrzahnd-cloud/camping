"""Buchung/Aufenthalt ohne fest zugeteilten Stellplatz (Typ, Platz als Freitext, Personen)

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-06 16:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.models.common


revision: str = '0007'
down_revision: Union[str, None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('buchung', 'stellplatz_id', existing_type=app.models.common.GUID(), nullable=True)
    op.add_column('buchung', sa.Column('stellplatz_typ', sa.String(length=50), nullable=True))
    op.add_column('buchung', sa.Column('platz', sa.String(length=50), nullable=True))
    op.add_column('buchung', sa.Column('anzahl_erwachsene', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('buchung', sa.Column('anzahl_kinder', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('buchung', sa.Column('bemerkung', sa.Text(), nullable=True))


def downgrade() -> None:
    for spalte in ('bemerkung', 'anzahl_kinder', 'anzahl_erwachsene', 'platz', 'stellplatz_typ'):
        op.drop_column('buchung', spalte)
    op.alter_column('buchung', 'stellplatz_id', existing_type=app.models.common.GUID(), nullable=False)
