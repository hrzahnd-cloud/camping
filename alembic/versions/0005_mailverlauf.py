"""Mailverlauf je Reservationsanfrage (eingehend/ausgehend aus dem Postfach)

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-03 14:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.models.common


revision: str = '0005'
down_revision: Union[str, None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'mail_nachricht',
        sa.Column('reservationsanfrage_id', app.models.common.GUID(), nullable=True),
        sa.Column('richtung', sa.String(length=10), nullable=False),
        sa.Column('message_id', sa.String(length=255), nullable=False),
        sa.Column('in_reply_to', sa.String(length=255), nullable=True),
        sa.Column('verweise', sa.Text(), nullable=True),
        sa.Column('von', sa.String(length=255), nullable=False),
        sa.Column('an', sa.String(length=500), nullable=True),
        sa.Column('betreff', sa.String(length=300), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('datum', sa.DateTime(timezone=True), nullable=False),
        sa.Column('weitergeleitet', sa.Boolean(), nullable=False),
        sa.Column('gelesen', sa.Boolean(), nullable=False),
        sa.Column('id', app.models.common.GUID(), nullable=False),
        sa.Column('erstellt_am', sa.DateTime(timezone=True), nullable=False),
        sa.Column('geaendert_am', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['reservationsanfrage_id'], ['reservationsanfrage.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('message_id'),
    )
    op.create_index('ix_mail_nachricht_reservationsanfrage_id', 'mail_nachricht', ['reservationsanfrage_id'])


def downgrade() -> None:
    op.drop_index('ix_mail_nachricht_reservationsanfrage_id', table_name='mail_nachricht')
    op.drop_table('mail_nachricht')
