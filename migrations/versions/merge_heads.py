"""merge heads

Revision ID: merge_heads
Revises: add_session_id, fix_sequences
Create Date: 2024-02-23 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'merge_heads'
down_revision = ('add_session_id', 'fix_sequences')
branch_labels = None
depends_on = None

def upgrade():
    pass

def downgrade():
    pass