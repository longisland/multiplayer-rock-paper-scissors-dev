"""add telegram fields

Revision ID: 20240120_add_telegram_fields
Revises: 
Create Date: 2024-01-20 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20240120_add_telegram_fields'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('users', sa.Column('telegram_id', sa.BigInteger(), nullable=True))
    op.add_column('users', sa.Column('telegram_username', sa.String(length=80), nullable=True))
    op.add_column('users', sa.Column('telegram_first_name', sa.String(length=80), nullable=True))
    op.add_column('users', sa.Column('telegram_last_name', sa.String(length=80), nullable=True))
    op.add_column('users', sa.Column('telegram_auth_date', sa.DateTime(), nullable=True))
    op.create_index(op.f('ix_users_telegram_id'), 'users', ['telegram_id'], unique=True)

def downgrade():
    op.drop_index(op.f('ix_users_telegram_id'), table_name='users')
    op.drop_column('users', 'telegram_auth_date')
    op.drop_column('users', 'telegram_last_name')
    op.drop_column('users', 'telegram_first_name')
    op.drop_column('users', 'telegram_username')
    op.drop_column('users', 'telegram_id')