"""Laufnummer und verlangte Anzahlung je Reservationsanfrage

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-06 14:30:00

Bestehende Anfragen werden je Eingangsjahr in der Reihenfolge ihres
Eingangs nachnummeriert (2026-001, 2026-002, …).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0006'
down_revision: Union[str, None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('reservationsanfrage', sa.Column('nummer', sa.String(length=20), nullable=True))
    op.add_column('reservationsanfrage', sa.Column('anzahlung_verlangt', sa.Numeric(precision=10, scale=2), nullable=True))

    verbindung = op.get_bind()
    tabelle = sa.table('reservationsanfrage', sa.column('id'), sa.column('eingangs_datum'), sa.column('nummer'))
    zaehler: dict[int, int] = {}
    for zeile in verbindung.execute(sa.select(tabelle.c.id, tabelle.c.eingangs_datum)
                                    .order_by(tabelle.c.eingangs_datum, tabelle.c.id)).all():
        jahr = zeile.eingangs_datum.year
        zaehler[jahr] = zaehler.get(jahr, 0) + 1
        verbindung.execute(sa.update(tabelle).where(tabelle.c.id == zeile.id)
                           .values(nummer=f"{jahr}-{zaehler[jahr]:03d}"))

    op.create_index('ix_reservationsanfrage_nummer', 'reservationsanfrage', ['nummer'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_reservationsanfrage_nummer', table_name='reservationsanfrage')
    op.drop_column('reservationsanfrage', 'anzahlung_verlangt')
    op.drop_column('reservationsanfrage', 'nummer')
