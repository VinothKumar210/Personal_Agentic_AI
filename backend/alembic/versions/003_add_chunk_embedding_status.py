"""add chunk embedding status

Revision ID: 003
Revises: 002
Create Date: 2026-06-18 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('document_chunks', sa.Column('embedding_status', sa.String(), server_default='pending', nullable=False))
    op.add_column('document_chunks', sa.Column('embedding_error', sa.Text(), nullable=True))
    op.add_column('document_chunks', sa.Column('embedded_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_document_chunks_embedding_status'), 'document_chunks', ['embedding_status'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_document_chunks_embedding_status'), table_name='document_chunks')
    op.drop_column('document_chunks', 'embedded_at')
    op.drop_column('document_chunks', 'embedding_error')
    op.drop_column('document_chunks', 'embedding_status')
