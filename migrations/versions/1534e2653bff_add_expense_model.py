"""Add expense model

Revision ID: 1534e2653bff
Revises: c3d9e8f4a2b1
Create Date: 2026-10-24 14:10:30.596699
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = '1534e2653bff'
down_revision = 'c3d9e8f4a2b1'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = inspector.get_table_names()

    if 'expenses' not in tables:
        op.create_table(
            'expenses',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('type', sa.Enum('servicio', 'gasto', 'ingreso', name='expense_type'), nullable=False),
            sa.Column('amount', sa.Float(), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('date', sa.Date(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.CheckConstraint('amount > 0', name='ck_expense_amount_positive'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        with op.batch_alter_table('expenses', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_expenses_user_date'), ['user_id', 'date'])


def downgrade():
    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_expenses_user_date'))

    op.drop_table('expenses')
    # En PostgreSQL los tipos ENUM son objetos independientes del esquema y
    # sobreviven a un DROP TABLE: hay que eliminarlos explícitamente.
    sa.Enum(name='expense_type').drop(op.get_bind(), checkfirst=True)
