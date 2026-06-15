from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "issues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("user_name", sa.String(length=120), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("summary", sa.String(length=220), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("district", sa.String(length=40), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("address_text", sa.String(length=255), nullable=True),
        sa.Column("photo_path", sa.String(length=255), nullable=True),
        sa.Column("photo_evidence", sa.Boolean(), nullable=False),
        sa.Column("resolution_photo_path", sa.String(length=255), nullable=True),
        sa.Column("resolution_comment", sa.Text(), nullable=True),
        sa.Column("priority_score", sa.Integer(), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("ai_confidence", sa.Integer(), nullable=False),
        sa.Column("ai_mode", sa.String(length=32), nullable=False),
        sa.Column("ai_explanation", sa.Text(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("responsible_service", sa.String(length=120), nullable=False),
        sa.Column("assigned_to", sa.String(length=120), nullable=True),
        sa.Column("sla_due_at", sa.DateTime(), nullable=True),
        sa.Column("sla_status", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_issues_id"), "issues", ["id"], unique=False)
    op.create_index(op.f("ix_issues_source"), "issues", ["source"], unique=False)
    op.create_index(op.f("ix_issues_category"), "issues", ["category"], unique=False)
    op.create_index(op.f("ix_issues_district"), "issues", ["district"], unique=False)
    op.create_index(op.f("ix_issues_latitude"), "issues", ["latitude"], unique=False)
    op.create_index(op.f("ix_issues_longitude"), "issues", ["longitude"], unique=False)
    op.create_index(op.f("ix_issues_priority_score"), "issues", ["priority_score"], unique=False)
    op.create_index(op.f("ix_issues_risk_level"), "issues", ["risk_level"], unique=False)
    op.create_index(op.f("ix_issues_responsible_service"), "issues", ["responsible_service"], unique=False)
    op.create_index(op.f("ix_issues_ai_mode"), "issues", ["ai_mode"], unique=False)
    op.create_index(op.f("ix_issues_assigned_to"), "issues", ["assigned_to"], unique=False)
    op.create_index(op.f("ix_issues_sla_due_at"), "issues", ["sla_due_at"], unique=False)
    op.create_index(op.f("ix_issues_sla_status"), "issues", ["sla_status"], unique=False)
    op.create_index(op.f("ix_issues_status"), "issues", ["status"], unique=False)
    op.create_index(op.f("ix_issues_resolved_at"), "issues", ["resolved_at"], unique=False)
    op.create_index(op.f("ix_issues_created_at"), "issues", ["created_at"], unique=False)

    op.create_table(
        "duplicate_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("issue_id", sa.Integer(), nullable=False),
        sa.Column("duplicate_issue_id", sa.Integer(), nullable=False),
        sa.Column("similarity_score", sa.Float(), nullable=False),
        sa.Column("distance_meters", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["duplicate_issue_id"], ["issues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["issue_id"], ["issues.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_duplicate_links_id"), "duplicate_links", ["id"], unique=False)
    op.create_index(op.f("ix_duplicate_links_issue_id"), "duplicate_links", ["issue_id"], unique=False)
    op.create_index(
        op.f("ix_duplicate_links_duplicate_issue_id"),
        "duplicate_links",
        ["duplicate_issue_id"],
        unique=False,
    )

    op.create_table(
        "status_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("issue_id", sa.Integer(), nullable=False),
        sa.Column("old_status", sa.String(length=24), nullable=True),
        sa.Column("new_status", sa.String(length=24), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["issue_id"], ["issues.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_status_history_id"), "status_history", ["id"], unique=False)
    op.create_index(op.f("ix_status_history_issue_id"), "status_history", ["issue_id"], unique=False)
    op.create_index(op.f("ix_status_history_created_at"), "status_history", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_status_history_created_at"), table_name="status_history")
    op.drop_index(op.f("ix_status_history_issue_id"), table_name="status_history")
    op.drop_index(op.f("ix_status_history_id"), table_name="status_history")
    op.drop_table("status_history")
    op.drop_index(op.f("ix_duplicate_links_duplicate_issue_id"), table_name="duplicate_links")
    op.drop_index(op.f("ix_duplicate_links_issue_id"), table_name="duplicate_links")
    op.drop_index(op.f("ix_duplicate_links_id"), table_name="duplicate_links")
    op.drop_table("duplicate_links")
    op.drop_index(op.f("ix_issues_created_at"), table_name="issues")
    op.drop_index(op.f("ix_issues_status"), table_name="issues")
    op.drop_index(op.f("ix_issues_resolved_at"), table_name="issues")
    op.drop_index(op.f("ix_issues_risk_level"), table_name="issues")
    op.drop_index(op.f("ix_issues_sla_status"), table_name="issues")
    op.drop_index(op.f("ix_issues_sla_due_at"), table_name="issues")
    op.drop_index(op.f("ix_issues_assigned_to"), table_name="issues")
    op.drop_index(op.f("ix_issues_ai_mode"), table_name="issues")
    op.drop_index(op.f("ix_issues_responsible_service"), table_name="issues")
    op.drop_index(op.f("ix_issues_priority_score"), table_name="issues")
    op.drop_index(op.f("ix_issues_longitude"), table_name="issues")
    op.drop_index(op.f("ix_issues_latitude"), table_name="issues")
    op.drop_index(op.f("ix_issues_district"), table_name="issues")
    op.drop_index(op.f("ix_issues_category"), table_name="issues")
    op.drop_index(op.f("ix_issues_source"), table_name="issues")
    op.drop_index(op.f("ix_issues_id"), table_name="issues")
    op.drop_table("issues")
