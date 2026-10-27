"""add topic clusters

Revision ID: 006
Revises: 005
Create Date: 2026-06-22 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'topic_clusters',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('keywords_json', sa.Text(), nullable=True),
        sa.Column('document_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('chunk_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'cluster_assignments',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('cluster_id', sa.String(), nullable=False),
        sa.Column('document_id', sa.String(), nullable=False),
        sa.Column('chunk_id', sa.String(), nullable=True),
        sa.Column('score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['chunk_id'], ['document_chunks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['cluster_id'], ['topic_clusters.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_cluster_assignments_chunk_id'), 'cluster_assignments', ['chunk_id'], unique=False)
    op.create_index(op.f('ix_cluster_assignments_cluster_id'), 'cluster_assignments', ['cluster_id'], unique=False)
    op.create_index(op.f('ix_cluster_assignments_document_id'), 'cluster_assignments', ['document_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_cluster_assignments_document_id'), table_name='cluster_assignments')
    op.drop_index(op.f('ix_cluster_assignments_cluster_id'), table_name='cluster_assignments')
    op.drop_index(op.f('ix_cluster_assignments_chunk_id'), table_name='cluster_assignments')
    op.drop_table('cluster_assignments')
    op.drop_table('topic_clusters')
