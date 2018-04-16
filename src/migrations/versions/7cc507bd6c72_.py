"""linked submissions

Revision ID: 7cc507bd6c72
Revises: 08eb5c3b5177
Create Date: 2018-04-16 11:28:02.463733

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7cc507bd6c72'
down_revision = '08eb5c3b5177'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('saved_submission', schema=None) as batch_op:
        batch_op.add_column(sa.Column('master', sa.Boolean(), nullable=False))

    with op.batch_alter_table('submission_group', schema=None) as batch_op:
        batch_op.add_column(sa.Column('grouped', sa.Boolean(), nullable=True))


def downgrade():
    with op.batch_alter_table('submission_group', schema=None) as batch_op:
        batch_op.drop_column('grouped')

    with op.batch_alter_table('saved_submission', schema=None) as batch_op:
        batch_op.drop_column('master')
