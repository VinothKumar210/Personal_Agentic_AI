"""add personal memories table

Revision ID: 011
Revises: 010
Create Date: 2026-07-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'personal_memories',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('privacy_level', sa.String(), nullable=False),
        sa.Column('source_citation', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_personal_memories_user_id'), 'personal_memories', ['user_id'], unique=False)

def downgrade():
    op.drop_index(op.f('ix_personal_memories_user_id'), table_name='personal_memories')
    op.drop_table('personal_memories')
