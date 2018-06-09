"""initial tables

Revision ID: da88034f27d3
Revises:
Create Date: 2018-03-21 11:00:02.270541

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'da88034f27d3'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'notice',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('text', sa.String(length=500), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'site',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_table(
        'user',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=16), nullable=False),
        sa.Column('password', sa.String(length=120), nullable=False),
        sa.Column('dark_theme', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
    )
    op.create_table(
        'account',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('site_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=120), nullable=False),
        sa.Column('credentials', sa.LargeBinary(), nullable=False),
        sa.Column('used_last', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['site_id'], ['site.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'notice_viewed',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('notice_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['notice_id'], ['notice.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'saved_submission',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tags', sa.Text(), nullable=True),
        sa.Column(
            'rating',
            sa.Enum('general', 'mature', 'explicit', name='rating'),
            nullable=True,
        ),
        sa.Column('original_filename', sa.String(length=1000), nullable=True),
        sa.Column('image_filename', sa.String(length=1000), nullable=True),
        sa.Column('image_mimetype', sa.String(length=50), nullable=True),
        sa.Column('account_ids', sa.String(length=1000), nullable=True),
        sa.Column('site_data', sa.Text(), nullable=True),
        sa.Column('submitted', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'account_config',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=120), nullable=False),
        sa.Column('val', sa.String(length=120), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['account.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('account_config')
    op.drop_table('saved_submission')
    op.drop_table('notice_viewed')
    op.drop_table('account')
    op.drop_table('user')
    op.drop_table('site')
    op.drop_table('notice')
