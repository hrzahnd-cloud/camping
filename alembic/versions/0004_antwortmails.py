"""Einstellungen (Signatur, IBAN, TWINT) und eindeutige Mailvorlagen je Typ/Sprache

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-28 14:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0004'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'app_einstellung',
        sa.Column('schluessel', sa.String(length=60), nullable=False),
        sa.Column('wert', sa.Text(), nullable=False),
        sa.Column('geaendert_am', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('schluessel'),
    )
    with op.batch_alter_table('email_vorlage') as tabelle:
        tabelle.create_unique_constraint('uq_email_vorlage_typ_sprache', ['typ', 'sprache'])


def downgrade() -> None:
    with op.batch_alter_table('email_vorlage') as tabelle:
        tabelle.drop_constraint('uq_email_vorlage_typ_sprache', type_='unique')
    op.drop_table('app_einstellung')
