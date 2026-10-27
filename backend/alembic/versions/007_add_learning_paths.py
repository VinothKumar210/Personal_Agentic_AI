"""add learning paths

Revision ID: 007
Revises: 006
Create Date: 2026-06-22 13:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'learning_profiles',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('goal_title', sa.String(), nullable=False),
        sa.Column('target_role', sa.String(), nullable=True),
        sa.Column('current_level', sa.String(), nullable=True),
        sa.Column('focus_keywords_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'learning_recommendations',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('profile_id', sa.String(), nullable=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('evidence_json', sa.Text(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='open'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['profile_id'], ['learning_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_learning_recommendations_profile_id'), 'learning_recommendations', ['profile_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_learning_recommendations_profile_id'), table_name='learning_recommendations')
    op.drop_table('learning_recommendations')
    op.drop_table('learning_profiles')
