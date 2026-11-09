"""Saisons je Jahr: Vor-, Haupt- und Nachsaison getrennt; 2027 aus 2026

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-09 16:30:00

Bisher gab es «Hauptsaison 2026» (1.7.–30.8.) und eine gemeinsame
«Vor-/Nachsaison 2026» (1.5.–30.9.), die die Hauptsaison überdeckte. Neu (mit
dem Betrieb festgelegt, November 2026): Vorsaison 1.5.–30.6., Hauptsaison
1.7.–31.8., Nachsaison 1.9.–30.9. Die Nachsaison übernimmt die Preise der
bisherigen Vor-/Nachsaison. Fehlt 2027, wird es aus 2026 übernommen (gleiche
Preise wie auf camping-aeschi.ch/preise-2 für 2027).
"""
import uuid
from datetime import date, datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.models.common


revision: str = '0010'
down_revision: Union[str, None] = '0009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DATEN = {'vorsaison': ((5, 1), (6, 30), 'Vorsaison'), 'hauptsaison': ((7, 1), (8, 31), 'Hauptsaison'),
         'nachsaison': ((9, 1), (9, 30), 'Nachsaison')}


def upgrade() -> None:
    op.add_column('saison', sa.Column('typ', sa.String(length=20), nullable=True))
    con = op.get_bind()
    meta = sa.MetaData()
    saison = sa.Table('saison', meta, sa.Column('id', app.models.common.GUID()), sa.Column('typ', sa.String),
                      sa.Column('bezeichnung', sa.String), sa.Column('gueltig_ab', sa.Date), sa.Column('gueltig_bis', sa.Date),
                      sa.Column('erstellt_am', sa.DateTime(timezone=True)), sa.Column('geaendert_am', sa.DateTime(timezone=True)))
    preis = sa.Table('artikel_preis', meta, sa.Column('id', app.models.common.GUID()), sa.Column('artikel_id', app.models.common.GUID()),
                     sa.Column('saison_id', app.models.common.GUID()), sa.Column('preis', sa.Numeric(8, 2)),
                     sa.Column('erstellt_am', sa.DateTime(timezone=True)), sa.Column('geaendert_am', sa.DateTime(timezone=True)))
    jetzt = datetime.now(timezone.utc)

    def setze(sid, typ, jahr):
        (m1, d1), (m2, d2), name = DATEN[typ]
        con.execute(saison.update().where(saison.c.id == sid).values(
            typ=typ, bezeichnung=f'{name} {jahr}', gueltig_ab=date(jahr, m1, d1), gueltig_bis=date(jahr, m2, d2), geaendert_am=jetzt))

    def neu(typ, jahr, preise):
        (m1, d1), (m2, d2), name = DATEN[typ]
        sid = uuid.uuid4()
        con.execute(saison.insert().values(id=sid, typ=typ, bezeichnung=f'{name} {jahr}', gueltig_ab=date(jahr, m1, d1),
                                           gueltig_bis=date(jahr, m2, d2), erstellt_am=jetzt, geaendert_am=jetzt))
        for artikel_id, betrag in preise:
            con.execute(preis.insert().values(id=uuid.uuid4(), artikel_id=artikel_id, saison_id=sid, preis=betrag,
                                              erstellt_am=jetzt, geaendert_am=jetzt))

    def preise_von(sid):
        return [(r.artikel_id, r.preis) for r in con.execute(sa.select(preis.c.artikel_id, preis.c.preis).where(preis.c.saison_id == sid))]

    for s in list(con.execute(sa.select(saison))):
        jahr, name = s.gueltig_ab.year, (s.bezeichnung or '').lower()
        if name.startswith('haupt'):
            setze(s.id, 'hauptsaison', jahr)
        elif name.startswith('vor'):
            setze(s.id, 'vorsaison', jahr)
            if '/nach' in name or 'nach' in name:
                neu('nachsaison', jahr, preise_von(s.id))
        elif name.startswith('nach'):
            setze(s.id, 'nachsaison', jahr)

    # Altersgruppe wie mit dem Betrieb festgelegt: Kleinkinder 0–5 Jahre
    artikel = sa.Table('artikel', meta, sa.Column('code', sa.String), sa.Column('bezeichnung', sa.String))
    con.execute(artikel.update().where(artikel.c.code == 'KLEINKINDER', artikel.c.bezeichnung == 'Kleinkinder (2-5 Jahre)')
                .values(bezeichnung='Kleinkinder (0–5 Jahre)'))

    jahre = {}
    for s in con.execute(sa.select(saison).where(saison.c.typ.is_not(None))):
        jahre.setdefault(s.gueltig_ab.year, {})[s.typ] = s.id
    if 2026 in jahre and 2027 not in jahre:
        for typ, sid in jahre[2026].items():
            neu(typ, 2027, preise_von(sid))


def downgrade() -> None:
    op.drop_column('saison', 'typ')
