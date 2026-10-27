"""Modul-Schalter für die Bedienoberfläche

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-27 16:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'modul_einstellung',
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('aktiv', sa.Boolean(), nullable=False),
        sa.Column('geaendert_am', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('code'),
    )


def downgrade() -> None:
    op.drop_table('modul_einstellung')
