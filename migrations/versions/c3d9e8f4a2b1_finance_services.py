"""finance_services table

Revision ID: c3d9e8f4a2b1
Revises: 4c9fb569915e
Create Date: 2026-10-24 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'c3d9e8f4a2b1'
down_revision = '4c9fb569915e'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = inspector.get_table_names()

    # Añadir columna dinero_disponible a users si no existe
    user_cols = [c['name'] for c in inspector.get_columns('users')]
    if 'dinero_disponible' not in user_cols:
        with op.batch_alter_table('users', schema=None) as batch_op:
            batch_op.add_column(sa.Column('dinero_disponible', sa.Float(), nullable=False, server_default='0.0'))

    # Crear tabla finance_services si no existe
    if 'finance_services' not in tables:
        op.create_table(
            'finance_services',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('servicio', sa.String(length=120), nullable=False),
            sa.Column('importe', sa.Float(), nullable=False, server_default='0.0'),
            sa.Column('fecha_vencimiento', sa.Date(), nullable=False),
            sa.Column('pagado', sa.Boolean(), nullable=False, server_default='0'),
            sa.Column('fecha_pago', sa.Date(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        with op.batch_alter_table('finance_services', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_finance_services_user_id'), ['user_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_finance_services_fecha_vencimiento'), ['fecha_vencimiento'], unique=False)


def downgrade():
    with op.batch_alter_table('finance_services', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_finance_services_user_id'))
        batch_op.drop_index(batch_op.f('ix_finance_services_fecha_vencimiento'))

    op.drop_table('finance_services')

    bind = op.get_bind()
    inspector = inspect(bind)
    user_cols = [c['name'] for c in inspector.get_columns('users')]
    if 'dinero_disponible' in user_cols:
        with op.batch_alter_table('users', schema=None) as batch_op:
            batch_op.drop_column('dinero_disponible')
