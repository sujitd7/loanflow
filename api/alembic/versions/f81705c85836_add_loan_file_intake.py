"""add loan-file intake tables

Revision ID: f81705c85836
Revises: bd693f8a6bb0
Create Date: 2026-09-05

Adds loan_files, loan_documents, review_tasks and task_events for P2
(loan-file intake + task generation).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f81705c85836"
down_revision: str | None = "bd693f8a6bb0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

loan_file_status = sa.Enum(
    "DRAFT",
    "SUBMITTED",
    "IN_REVIEW",
    "FUND_READY_TO_RELEASE",
    "PURGED",
    name="loan_file_status",
)
product_type = sa.Enum(
    "TERM_LOAN",
    "LINE_OF_CREDIT",
    "MORTGAGE",
    "AUTO_LOAN",
    "PERSONAL_LOAN",
    name="product_type",
)
document_kind = sa.Enum(
    "IDENTITY",
    "INCOME_PROOF",
    "BANK_STATEMENT",
    "TAX_RETURN",
    "COLLATERAL",
    "OTHER",
    name="document_kind",
)
review_task_status = sa.Enum(
    "PENDING_MAKER",
    "PENDING_CHECKER",
    "COMPLETED",
    "CHANGES_REQUESTED",
    name="review_task_status",
)
check_type = sa.Enum(
    "CREDIT_VALIDATION",
    "KYC_VERIFICATION",
    "PAYMENT_ELIGIBILITY",
    "TAX_RETURN_VERIFICATION",
    name="check_type",
)


def upgrade() -> None:
    op.create_table(
        "loan_files",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("status", loan_file_status, server_default="DRAFT", nullable=False),
        sa.Column("product_type", product_type, nullable=False),
        sa.Column("loan_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False),
        sa.Column("applicant_full_name", sa.String(length=200), nullable=False),
        sa.Column("applicant_email", sa.String(length=320), nullable=False),
        sa.Column("applicant_dob", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fund_ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("loan_amount >= 0", name="ck_loan_files_amount_nonneg"),
    )
    op.create_index(
        op.f("ix_loan_files_created_by_id"), "loan_files", ["created_by_id"], unique=False
    )
    op.create_index(
        "ix_loan_files_status_fund_ready_at",
        "loan_files",
        ["status", "fund_ready_at"],
        unique=False,
    )

    op.create_table(
        "loan_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("loan_file_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("kind", document_kind, nullable=True),
        sa.Column("uploaded_by_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["loan_file_id"], ["loan_files.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("loan_file_id", "sha256", name="uq_loan_documents_file_sha"),
    )
    op.create_index(
        op.f("ix_loan_documents_loan_file_id"), "loan_documents", ["loan_file_id"], unique=False
    )

    op.create_table(
        "review_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("loan_file_id", sa.Integer(), nullable=False),
        sa.Column("check_type", check_type, nullable=False),
        sa.Column(
            "status",
            review_task_status,
            server_default="PENDING_MAKER",
            nullable=False,
        ),
        sa.Column("maker_id", sa.Integer(), nullable=False),
        sa.Column("checker_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("findings", sa.Text(), nullable=True),
        sa.Column("checker_comment", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["loan_file_id"], ["loan_files.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["maker_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["checker_id"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("checker_id <> maker_id", name="ck_review_tasks_checker_ne_maker"),
        sa.UniqueConstraint("loan_file_id", "check_type", name="uq_review_tasks_file_check"),
    )
    op.create_index(
        op.f("ix_review_tasks_loan_file_id"), "review_tasks", ["loan_file_id"], unique=False
    )
    op.create_index(
        "ix_review_tasks_maker_id_status", "review_tasks", ["maker_id", "status"], unique=False
    )
    op.create_index(
        "ix_review_tasks_checker_id_status",
        "review_tasks",
        ["checker_id", "status"],
        unique=False,
    )

    op.create_table(
        "task_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("loan_file_id", sa.Integer(), nullable=False),
        sa.Column("review_task_id", sa.Integer(), nullable=True),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("from_status", sa.String(length=40), nullable=True),
        sa.Column("to_status", sa.String(length=40), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["loan_file_id"], ["loan_files.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["review_task_id"], ["review_tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_task_events_loan_file_id_created_at",
        "task_events",
        ["loan_file_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_task_events_loan_file_id_created_at", table_name="task_events")
    op.drop_table("task_events")

    op.drop_index("ix_review_tasks_checker_id_status", table_name="review_tasks")
    op.drop_index("ix_review_tasks_maker_id_status", table_name="review_tasks")
    op.drop_index(op.f("ix_review_tasks_loan_file_id"), table_name="review_tasks")
    op.drop_table("review_tasks")

    op.drop_index(op.f("ix_loan_documents_loan_file_id"), table_name="loan_documents")
    op.drop_table("loan_documents")

    op.drop_index("ix_loan_files_status_fund_ready_at", table_name="loan_files")
    op.drop_index(op.f("ix_loan_files_created_by_id"), table_name="loan_files")
    op.drop_table("loan_files")

    bind = op.get_bind()
    check_type.drop(bind, checkfirst=True)
    review_task_status.drop(bind, checkfirst=True)
    document_kind.drop(bind, checkfirst=True)
    product_type.drop(bind, checkfirst=True)
    loan_file_status.drop(bind, checkfirst=True)
