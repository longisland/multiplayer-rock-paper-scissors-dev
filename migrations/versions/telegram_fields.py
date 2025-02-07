"""Add Telegram fields to User model

Revision ID: telegram_fields
Revises: 1a2b3c4d5e6f
Create Date: 2024-02-07 12:45:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'telegram_fields'
down_revision = '1a2b3c4d5e6f'
branch_labels = None
depends_on = None

def upgrade():
    # Add Telegram fields to User model
    op.add_column('users', sa.Column('telegram_id', sa.BigInteger(), unique=True))
    op.add_column('users', sa.Column('telegram_username', sa.String(80)))
    op.add_column('users', sa.Column('telegram_first_name', sa.String(80)))
    op.add_column('users', sa.Column('telegram_last_name', sa.String(80)))

def downgrade():
    # Remove Telegram fields from User model
    op.drop_column('users', 'telegram_last_name')
    op.drop_column('users', 'telegram_first_name')
    op.drop_column('users', 'telegram_username')
    op.drop_column('users', 'telegram_id')