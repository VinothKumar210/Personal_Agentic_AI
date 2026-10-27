"""collection tag composite unique

Revision ID: 010
Revises: 009
Create Date: 2026-06-23 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None

def upgrade():
    if op.get_bind().dialect.name == "sqlite":
        return

    # Postgres supports dropping constraints and indexes gracefully with IF EXISTS.
    # Since we already return early for SQLite, we can just use raw SQL or standard ops.
    op.execute("ALTER TABLE collections DROP CONSTRAINT IF EXISTS collections_name_key")
    op.execute("DROP INDEX IF EXISTS ix_collections_name")
    
    # Create the new constraint
    op.create_unique_constraint('uix_collection_user_name', 'collections', ['user_id', 'name'])

    # Do the same for tags
    op.execute("ALTER TABLE tags DROP CONSTRAINT IF EXISTS tags_name_key")
    op.execute("DROP INDEX IF EXISTS ix_tags_name")
    
    op.create_unique_constraint('uix_tag_user_name', 'tags', ['user_id', 'name'])

def downgrade():
    with op.batch_alter_table('tags') as batch_op:
        batch_op.drop_constraint('uix_tag_user_name', type_='unique')
        batch_op.create_unique_constraint('tags_name_key', ['name'])

    with op.batch_alter_table('collections') as batch_op:
        batch_op.drop_constraint('uix_collection_user_name', type_='unique')
        batch_op.create_unique_constraint('collections_name_key', ['name'])
