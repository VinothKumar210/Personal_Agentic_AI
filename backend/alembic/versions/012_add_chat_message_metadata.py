"""add metadata_json to chat_messages

Revision ID: 012
Revises: 011
Create Date: 2026-07-17 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '012'
down_revision = '011'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('chat_messages', sa.Column('metadata_json', sa.Text(), nullable=True))

def downgrade():
    op.drop_column('chat_messages', 'metadata_json')
