"""reset database schema

Revision ID: 1a2b3c4d5e6f
Revises: 
Create Date: 2024-03-20 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1a2b3c4d5e6f'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Drop existing tables if they exist
    op.drop_table('game_history', checkfirst=True)
    op.drop_table('users', checkfirst=True)

    # Create users table
    op.create_table('users',
        sa.Column('id', sa.Integer(), sa.Sequence('user_id_seq'), primary_key=True),
        sa.Column('username', sa.String(length=80), nullable=False),
        sa.Column('coins', sa.Integer(), nullable=True, default=100),
        sa.Column('created_at', sa.DateTime(), nullable=True, default=sa.func.now()),
        sa.Column('last_seen', sa.DateTime(), nullable=True, default=sa.func.now()),
        sa.Column('total_games', sa.Integer(), nullable=True, default=0),
        sa.Column('wins', sa.Integer(), nullable=True, default=0),
        sa.Column('losses', sa.Integer(), nullable=True, default=0),
        sa.Column('draws', sa.Integer(), nullable=True, default=0),
        sa.Column('total_coins_won', sa.Integer(), nullable=True, default=0),
        sa.Column('total_coins_lost', sa.Integer(), nullable=True, default=0),
        sa.UniqueConstraint('username')
    )

    # Create game_history table
    op.create_table('game_history',
        sa.Column('id', sa.Integer(), sa.Sequence('game_history_id_seq'), primary_key=True),
        sa.Column('player1_id', sa.Integer(), nullable=False),
        sa.Column('player2_id', sa.Integer(), nullable=False),
        sa.Column('player1_choice', sa.String(length=10), nullable=False),
        sa.Column('player2_choice', sa.String(length=10), nullable=False),
        sa.Column('winner_id', sa.Integer(), nullable=True),
        sa.Column('played_at', sa.DateTime(), nullable=True, default=sa.func.now()),
        sa.Column('bet_amount', sa.Integer(), nullable=True, default=0),
        sa.ForeignKeyConstraint(['player1_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['player2_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['winner_id'], ['users.id'], )
    )


def downgrade():
    op.drop_table('game_history')
    op.drop_table('users')