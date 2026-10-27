"""add users and ownership

Revision ID: 009
Revises: 008
Create Date: 2026-06-23 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import uuid

# revision identifiers, used by Alembic.
revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None

def generate_uuid():
    return str(uuid.uuid4())

def upgrade():
    # 1. Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('display_name', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    
    # Insert default dev user
    # Note: password is 'password' hashed with bcrypt
    dev_user_id = generate_uuid()
    # passlib.hash.bcrypt.hash("password") => we will just hardcode a valid hash for "password"
    dev_hashed_password = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjIQqiRQYq" 
    
    op.execute(f"""
        INSERT INTO users (id, email, hashed_password, display_name, is_active, created_at, updated_at) 
        VALUES ('{dev_user_id}', 'local@example.com', '{dev_hashed_password}', 'Local Dev', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """)

    # 2. Add nullable user_id to tables
    tables = [
        "documents",
        "ingestion_jobs",
        "topic_clusters",
        "learning_profiles",
        "learning_recommendations",
        "knowledge_nodes",
        "knowledge_edges",
        "conversations",
        "collections",
        "tags"
    ]
    
    for table in tables:
        op.add_column(table, sa.Column('user_id', sa.String(), nullable=True))
        
        # 3. Backfill existing records
        op.execute(f"UPDATE {table} SET user_id = '{dev_user_id}' WHERE user_id IS NULL")
        
        # SQLite doesn't natively support altering columns easily with Alembic alter_column to NOT NULL 
        # But we can do it via batch_alter_table
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column('user_id', nullable=False)
            batch_op.create_index(op.f(f'ix_{table}_user_id'), ['user_id'], unique=False)
            batch_op.create_foreign_key(f"fk_{table}_user_id", 'users', ['user_id'], ['id'], ondelete="CASCADE")

def downgrade():
    tables = [
        "tags",
        "collections",
        "conversations",
        "knowledge_edges",
        "knowledge_nodes",
        "learning_recommendations",
        "learning_profiles",
        "topic_clusters",
        "ingestion_jobs",
        "documents"
    ]
    for table in tables:
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_constraint(f"fk_{table}_user_id", type_="foreignkey")
            batch_op.drop_index(op.f(f'ix_{table}_user_id'))
            batch_op.drop_column('user_id')
            
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
