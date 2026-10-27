"""add knowledge graph

Revision ID: 008
Revises: 007
Create Date: 2026-06-22 14:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'knowledge_nodes',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('label', sa.String(), nullable=False),
        sa.Column('node_type', sa.String(), nullable=False, server_default='concept'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('aliases_json', sa.Text(), nullable=True),
        sa.Column('frequency', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'knowledge_edges',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('source_node_id', sa.String(), nullable=False),
        sa.Column('target_node_id', sa.String(), nullable=False),
        sa.Column('relation_type', sa.String(), nullable=False, server_default='related_to'),
        sa.Column('weight', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('evidence_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['source_node_id'], ['knowledge_nodes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['target_node_id'], ['knowledge_nodes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_knowledge_edges_source_node_id'), 'knowledge_edges', ['source_node_id'], unique=False)
    op.create_index(op.f('ix_knowledge_edges_target_node_id'), 'knowledge_edges', ['target_node_id'], unique=False)

    op.create_table(
        'knowledge_node_documents',
        sa.Column('node_id', sa.String(), nullable=False),
        sa.Column('document_id', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['node_id'], ['knowledge_nodes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('node_id', 'document_id')
    )


def downgrade():
    op.drop_table('knowledge_node_documents')
    op.drop_index(op.f('ix_knowledge_edges_target_node_id'), table_name='knowledge_edges')
    op.drop_index(op.f('ix_knowledge_edges_source_node_id'), table_name='knowledge_edges')
    op.drop_table('knowledge_edges')
    op.drop_table('knowledge_nodes')
