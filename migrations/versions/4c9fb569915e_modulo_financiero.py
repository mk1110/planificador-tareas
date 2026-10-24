"""modulo_financiero

Revision ID: 4c9fb569915e
Revises: ba0439e5bb03
Create Date: 2026-10-23 01:50:08.337470

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = '4c9fb569915e'
down_revision = 'ba0439e5bb03'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = inspector.get_table_names()

    if 'financial_movements' not in tables:
        op.create_table(
            'financial_movements',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('tipo', sa.Enum('ingreso', 'gasto', name='financial_movement_type'), nullable=False),
            sa.Column('categoria', sa.Enum('comida', 'alquiler', 'sueldo', 'proyectos', 'extras', 'servicios', 'compras', 'suministros', 'otro', name='financial_category'), nullable=False),
            sa.Column('monto', sa.Float(), nullable=False),
            sa.Column('fecha', sa.Date(), nullable=False),
            sa.Column('descripcion', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.CheckConstraint('monto > 0', name='ck_financial_movement_amount_positive'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        with op.batch_alter_table('financial_movements', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_financial_movements_fecha'), ['fecha'], unique=False)
            batch_op.create_index(batch_op.f('ix_financial_movements_user_id'), ['user_id'], unique=False)


def downgrade():
    with op.batch_alter_table('financial_movements', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_financial_movements_user_id'))
        batch_op.drop_index(batch_op.f('ix_financial_movements_fecha'))
    op.drop_table('financial_movements')
    sa.Enum(name='financial_category').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='financial_movement_type').drop(op.get_bind(), checkfirst=True)
