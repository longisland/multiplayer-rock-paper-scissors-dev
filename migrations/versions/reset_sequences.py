"""Reset sequences

Revision ID: reset_sequences
Revises: add_coin_tracking
Create Date: 2024-02-02 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'reset_sequences'
down_revision = 'add_coin_tracking'
branch_labels = None
depends_on = None


def upgrade():
    # Reset users sequence
    op.execute("""
        SELECT setval('users_id_seq', (SELECT MAX(id) FROM users));
    """)
    
    # Reset game_history sequence
    op.execute("""
        SELECT setval('game_history_id_seq', (SELECT MAX(id) FROM game_history));
    """)


def downgrade():
    pass