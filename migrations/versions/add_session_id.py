"""add session_id field

Revision ID: add_session_id
Revises: 
Create Date: 2024-02-23 19:55:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_session_id'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Add session_id column
    op.add_column('users', sa.Column('session_id', sa.String(80), nullable=True))
    
    # Make username nullable
    op.alter_column('users', 'username',
                    existing_type=sa.String(80),
                    nullable=True)
    
    # Create unique index on session_id
    op.create_unique_constraint('uq_users_session_id', 'users', ['session_id'])

def downgrade():
    # Drop unique constraint on session_id
    op.drop_constraint('uq_users_session_id', 'users', type_='unique')
    
    # Make username non-nullable again
    op.alter_column('users', 'username',
                    existing_type=sa.String(80),
                    nullable=False)
    
    # Drop session_id column
    op.drop_column('users', 'session_id')