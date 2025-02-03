from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column('game_history', sa.Column('is_auto_selected', sa.Boolean(), nullable=False, server_default='false'))

def downgrade():
    op.drop_column('game_history', 'is_auto_selected')