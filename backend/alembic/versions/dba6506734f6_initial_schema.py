"""initial schema

Revision ID: dba6506734f6
Revises:
Create Date: 2026-11-09 21:54:40.812938

"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "dba6506734f6"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "cv_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "job_offers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "analyses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("offer_id", sa.Uuid(), nullable=False),
        sa.Column("cv_document_id", sa.Uuid(), nullable=True),
        sa.Column("extraction", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("matches", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("salary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["cv_document_id"], ["cv_documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["offer_id"], ["job_offers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("offer_id"),
    )
    op.create_table(
        "applications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("offer_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "to_apply", "applied", "interview", "offer", "rejected", name="application_status"
            ),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["offer_id"], ["job_offers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("offer_id"),
    )
    op.create_table(
        "cv_chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.vector.VECTOR(dim=768), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["cv_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_cv_chunks_document_id"), "cv_chunks", ["document_id"], unique=False)
    # Approximate nearest-neighbour index for cosine similarity search over CV chunks.
    op.execute(
        "CREATE INDEX ix_cv_chunks_embedding ON cv_chunks USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_cv_chunks_embedding", table_name="cv_chunks")
    op.drop_index(op.f("ix_cv_chunks_document_id"), table_name="cv_chunks")
    op.drop_table("cv_chunks")
    op.drop_table("applications")
    op.drop_table("analyses")
    op.drop_table("job_offers")
    op.drop_table("cv_documents")
    sa.Enum(name="application_status").drop(op.get_bind(), checkfirst=True)
