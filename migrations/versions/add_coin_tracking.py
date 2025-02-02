"""add coin tracking

Revision ID: add_coin_tracking
Revises: 
Create Date: 2024-02-02 19:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_coin_tracking'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Add total_coins_won and total_coins_lost columns
    op.add_column('users', sa.Column('total_coins_won', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('users', sa.Column('total_coins_lost', sa.Integer(), nullable=True, server_default='0'))

def downgrade():
    # Remove the columns
    op.drop_column('users', 'total_coins_won')
    op.drop_column('users', 'total_coins_lost')