"""fix dependencies

Revision ID: fix_dependencies
Revises: 1a2b3c4d5e6f
Create Date: 2024-02-23 20:05:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'fix_dependencies'
down_revision = '1a2b3c4d5e6f'
branch_labels = None
depends_on = None

def upgrade():
    # Add session_id column
    op.add_column('users', sa.Column('session_id', sa.String(80), nullable=True))
    
    # Copy username to session_id for existing users
    op.execute("UPDATE users SET session_id = username")
    
    # Make username nullable
    op.alter_column('users', 'username',
                    existing_type=sa.String(80),
                    nullable=True)
    
    # Create unique index on session_id
    op.create_unique_constraint('uq_users_session_id', 'users', ['session_id'])
    
    # Make session_id non-nullable
    op.alter_column('users', 'session_id',
                    existing_type=sa.String(80),
                    nullable=False)

def downgrade():
    # Drop unique constraint on session_id
    op.drop_constraint('uq_users_session_id', 'users', type_='unique')
    
    # Make username non-nullable again
    op.alter_column('users', 'username',
                    existing_type=sa.String(80),
                    nullable=False)
    
    # Drop session_id column
    op.drop_column('users', 'session_id')