"""fix sequences

Revision ID: fix_sequences
Revises: telegram_fields
Create Date: 2024-02-07 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'fix_sequences'
down_revision = 'telegram_fields'
branch_labels = None
depends_on = None

def upgrade():
    # Drop existing sequences
    op.execute('DROP SEQUENCE IF EXISTS game_history_id_seq CASCADE')
    op.execute('DROP SEQUENCE IF EXISTS user_id_seq CASCADE')
    op.execute('DROP SEQUENCE IF EXISTS users_id_seq CASCADE')

    # Create new sequences
    op.execute('CREATE SEQUENCE users_id_seq START WITH 1')
    op.execute('CREATE SEQUENCE game_history_id_seq START WITH 1')

    # Update table sequences
    op.execute('ALTER TABLE users ALTER COLUMN id SET DEFAULT nextval(\'users_id_seq\')')
    op.execute('ALTER TABLE game_history ALTER COLUMN id SET DEFAULT nextval(\'game_history_id_seq\')')

    # Reset sequences to max value + 1
    op.execute('''
        SELECT setval('users_id_seq', COALESCE((SELECT MAX(id) + 1 FROM users), 1), false)
    ''')
    op.execute('''
        SELECT setval('game_history_id_seq', COALESCE((SELECT MAX(id) + 1 FROM game_history), 1), false)
    ''')

def downgrade():
    pass