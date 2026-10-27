"""add curation models and consolidation/pruning metadata

Revision ID: 013
Revises: 012
Create Date: 2026-07-18 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '013'
down_revision = '012'
branch_labels = None
depends_on = None

def upgrade():
    # Create curation_suggestions table
    op.create_table(
        'curation_suggestions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('suggestion_type', sa.String(), nullable=False),
        sa.Column('source_ids_json', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('proposed_payload_json', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.Column('provenance_metadata_json', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_curation_suggestions_user_id'), 'curation_suggestions', ['user_id'], unique=False)

    # Create curation_logs table
    op.create_table(
        'curation_logs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('sweep_type', sa.String(), nullable=False, server_default='dry_run'),
        sa.Column('items_processed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('items_merged', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('details_json', sa.Text(), nullable=True, server_default='{}'),
        sa.Column('status', sa.String(), nullable=False, server_default='completed'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_curation_logs_user_id'), 'curation_logs', ['user_id'], unique=False)

    # Create knowledge_briefings table
    op.create_table(
        'knowledge_briefings',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('summary_markdown', sa.Text(), nullable=False),
        sa.Column('highlights_json', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_knowledge_briefings_user_id'), 'knowledge_briefings', ['user_id'], unique=False)

    # Add consolidation columns to personal_memories
    op.add_column('personal_memories', sa.Column('consolidated_into_id', sa.String(), nullable=True))
    op.add_column('personal_memories', sa.Column('is_consolidated', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('personal_memories', sa.Column('last_consolidated_at', sa.DateTime(timezone=True), nullable=True))
    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key('fk_personal_memories_consolidated_into', 'personal_memories', 'personal_memories', ['consolidated_into_id'], ['id'], ondelete='SET NULL')

    # Add soft-pruning columns to knowledge_nodes
    op.add_column('knowledge_nodes', sa.Column('is_pruned', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('knowledge_nodes', sa.Column('pruned_reason', sa.Text(), nullable=True))
    op.add_column('knowledge_nodes', sa.Column('confidence_score', sa.Float(), nullable=False, server_default='1.0'))
    op.add_column('knowledge_nodes', sa.Column('last_reflected_at', sa.DateTime(timezone=True), nullable=True))

def downgrade():
    op.drop_column('knowledge_nodes', 'last_reflected_at')
    op.drop_column('knowledge_nodes', 'confidence_score')
    op.drop_column('knowledge_nodes', 'pruned_reason')
    op.drop_column('knowledge_nodes', 'is_pruned')

    op.drop_constraint('fk_personal_memories_consolidated_into', 'personal_memories', type_='foreignkey')
    op.drop_column('personal_memories', 'last_consolidated_at')
    op.drop_column('personal_memories', 'is_consolidated')
    op.drop_column('personal_memories', 'consolidated_into_id')

    op.drop_index(op.f('ix_knowledge_briefings_user_id'), table_name='knowledge_briefings')
    op.drop_table('knowledge_briefings')

    op.drop_index(op.f('ix_curation_logs_user_id'), table_name='curation_logs')
    op.drop_table('curation_logs')

    op.drop_index(op.f('ix_curation_suggestions_user_id'), table_name='curation_suggestions')
    op.drop_table('curation_suggestions')
