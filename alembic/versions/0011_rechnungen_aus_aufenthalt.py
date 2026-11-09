"""Rechnungen aus dem Aufenthalt: Anzahlung, Zahlungsart, Storno, Positionstext

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-09 17:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0011'
down_revision: Union[str, None] = '0010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('rechnung', sa.Column('anzahlung', sa.Numeric(10, 2), nullable=False, server_default='0'))
    op.add_column('rechnung', sa.Column('zahlungsart', sa.String(length=30), nullable=True))
    op.add_column('rechnung', sa.Column('bezahlt_am', sa.Date(), nullable=True))
    op.add_column('rechnung', sa.Column('storniert_am', sa.DateTime(timezone=True), nullable=True))
    op.add_column('rechnungsposition', sa.Column('bezeichnung', sa.String(length=200), nullable=True))
    op.add_column('rechnungsposition', sa.Column('reihenfolge', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    for spalte in ('reihenfolge', 'bezeichnung'):
        op.drop_column('rechnungsposition', spalte)
    for spalte in ('storniert_am', 'bezahlt_am', 'zahlungsart', 'anzahlung'):
        op.drop_column('rechnung', spalte)
