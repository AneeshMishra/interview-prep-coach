"""add criteria_breakdown_json to interview_summaries

Revision ID: b3f1a9c7d2e5
Revises: 8a1c7e4f2b3d
Create Date: 2026-09-12 17:00:00.000000

Per-criterion score breakdown for a completed interview (see
Rubric.average_criteria() in app/interview/rubric.py) — additive and
nullable, so existing summary rows just read back with no breakdown
rather than needing any backfill.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3f1a9c7d2e5'
down_revision: Union[str, None] = '8a1c7e4f2b3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('interview_summaries') as batch_op:
        batch_op.add_column(sa.Column('criteria_breakdown_json', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('interview_summaries') as batch_op:
        batch_op.drop_column('criteria_breakdown_json')
