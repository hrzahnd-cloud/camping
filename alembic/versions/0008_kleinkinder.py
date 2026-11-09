"""Kleinkinder (0–5 Jahre) getrennt von den Kindern (6–15 Jahre) erfassen

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-09 15:00:00

Bisher zählten Kleinkinder bei den Kindern mit. Für Preise (Kleinkinder gratis)
werden sie neu separat gespeichert. Bestehende Einträge bleiben unverändert
(Kleinkinder 0); die Aufteilung aus dem Homepage-Formular steht dort weiterhin
in der Bemerkung.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0008'
down_revision: Union[str, None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for tabelle in ('reservationsanfrage', 'buchung'):
        op.add_column(tabelle, sa.Column('anzahl_kleinkinder', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    for tabelle in ('reservationsanfrage', 'buchung'):
        op.drop_column(tabelle, 'anzahl_kleinkinder')
