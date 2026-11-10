"""Mails des BFS (HESTA-Zugangsdaten) getrennt von den Reservations-Mails

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-10 10:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0013'
down_revision: Union[str, None] = '0012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('mail_nachricht', sa.Column('kategorie', sa.String(length=20), nullable=True))
    op.create_index('ix_mail_nachricht_kategorie', 'mail_nachricht', ['kategorie'])


def downgrade() -> None:
    op.drop_index('ix_mail_nachricht_kategorie', table_name='mail_nachricht')
    op.drop_column('mail_nachricht', 'kategorie')
