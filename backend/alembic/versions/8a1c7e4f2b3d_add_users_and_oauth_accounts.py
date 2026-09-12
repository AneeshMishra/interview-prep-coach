"""add users and oauth_accounts; scope documents/chat/interview sessions by user

Revision ID: 8a1c7e4f2b3d
Revises: 3d08f97fd82f
Create Date: 2026-09-12 15:00:00.000000

Every document, chat session and interview session now belongs to a user
(app/db/models.py: Document.user_id, ChatSession.user_id,
InterviewSession.user_id). Rows created before multi-user support existed
have no owner, so this migration creates one seed/dev user and backfills
every pre-existing row onto it before tightening the new columns to
NOT NULL — nothing is dropped, real users simply start fresh from here.
"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8a1c7e4f2b3d'
down_revision: Union[str, None] = '3d08f97fd82f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SEED_USER_EMAIL = "dev-seed@interview-prep-coach.local"


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('display_name', sa.String(), nullable=True),
        sa.Column('avatar_url', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    op.create_table(
        'oauth_accounts',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('provider_account_id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider', 'provider_account_id', name='uq_oauth_provider_account'),
    )

    seed_user_id = str(uuid.uuid4())
    users_table = sa.table(
        'users',
        sa.column('id', sa.String()),
        sa.column('email', sa.String()),
        sa.column('display_name', sa.String()),
    )
    op.bulk_insert(users_table, [{
        'id': seed_user_id,
        'email': SEED_USER_EMAIL,
        'display_name': 'Seed User (pre-auth data)',
    }])

    for table_name in ('documents', 'chat_sessions', 'interview_sessions'):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.add_column(sa.Column('user_id', sa.String(), nullable=True))

        op.execute(
            f"UPDATE {table_name} SET user_id = '{seed_user_id}' WHERE user_id IS NULL"
        )

        with op.batch_alter_table(table_name) as batch_op:
            batch_op.alter_column('user_id', nullable=False)
            batch_op.create_foreign_key(
                f'fk_{table_name}_user_id_users', 'users', ['user_id'], ['id']
            )

    # content_hash dedup moves from global to per-user: two different users
    # uploading identical file content are independent knowledge bases now,
    # not a duplicate of each other.
    with op.batch_alter_table('documents') as batch_op:
        batch_op.drop_index(batch_op.f('ix_documents_content_hash'))
        batch_op.create_index(batch_op.f('ix_documents_content_hash'), ['content_hash'], unique=False)
        batch_op.create_unique_constraint(
            'uq_documents_user_content_hash', ['user_id', 'content_hash']
        )


def downgrade() -> None:
    with op.batch_alter_table('documents') as batch_op:
        batch_op.drop_constraint('uq_documents_user_content_hash', type_='unique')
        batch_op.drop_index(batch_op.f('ix_documents_content_hash'))
        batch_op.create_index(batch_op.f('ix_documents_content_hash'), ['content_hash'], unique=True)

    for table_name in ('documents', 'chat_sessions', 'interview_sessions'):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_constraint(f'fk_{table_name}_user_id_users', type_='foreignkey')
            batch_op.drop_column('user_id')

    op.drop_table('oauth_accounts')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
