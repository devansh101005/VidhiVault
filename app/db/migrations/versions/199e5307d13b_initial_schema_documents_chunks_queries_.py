"""initial schema: documents, chunks, queries, evaluation_pairs

Revision ID: 199e5307d13b
Revises:
Create Date: 2026-04-20 10:07:01.670947

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import pgvector

# revision identifiers, used by Alembic.
revision: str = '199e5307d13b'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        'documents',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('file_path', sa.String(), nullable=False),
        sa.Column('file_hash', sa.String(), nullable=False),
        sa.Column('total_pages', sa.Integer(), nullable=True),
        sa.Column('total_chunks', sa.Integer(), nullable=True),
        sa.Column('document_type', sa.String(), nullable=False),
        sa.Column(
            'processing_status',
            sa.Enum('pending', 'processing', 'completed', 'failed', name='processing_status_enum'),
            nullable=False,
        ),
        sa.Column('processing_error', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('file_hash'),
    )

    op.create_table(
        'evaluation_pairs',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('query_text', sa.Text(), nullable=False),
        sa.Column('relevant_chunk_ids', postgresql.ARRAY(sa.UUID()), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'queries',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('query_text', sa.Text(), nullable=False),
        sa.Column('response_text', sa.Text(), nullable=True),
        sa.Column('retrieved_chunk_ids', postgresql.ARRAY(sa.UUID()), nullable=True),
        sa.Column('reranked_chunk_ids', postgresql.ARRAY(sa.UUID()), nullable=True),
        sa.Column('model_used', sa.String(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('retrieval_latency_ms', sa.Integer(), nullable=True),
        sa.Column('generation_latency_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'chunks',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('document_id', sa.UUID(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('section_header', sa.String(), nullable=True),
        sa.Column('chunk_type', sa.String(), nullable=False),
        sa.Column('token_count', sa.Integer(), nullable=True),
        sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=384), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_index('idx_chunks_document_id', 'chunks', ['document_id'])
    op.execute(
        "CREATE INDEX idx_chunks_embedding ON chunks USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "ALTER TABLE chunks ADD COLUMN content_tsv tsvector "
        "GENERATED ALWAYS AS (to_tsvector('english', content)) STORED"
    )
    op.execute("CREATE INDEX idx_chunks_content_tsv ON chunks USING gin(content_tsv)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_chunks_content_tsv")
    op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS content_tsv")
    op.execute("DROP INDEX IF EXISTS idx_chunks_embedding")
    op.drop_index('idx_chunks_document_id', table_name='chunks')
    op.drop_table('chunks')
    op.drop_table('queries')
    op.drop_table('evaluation_pairs')
    op.drop_table('documents')
    op.execute("DROP TYPE IF EXISTS processing_status_enum")
    op.execute("DROP EXTENSION IF EXISTS vector")
