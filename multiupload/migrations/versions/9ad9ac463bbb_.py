"""email verify information

Revision ID: 9ad9ac463bbb
Revises: 34454fe8fd61
Create Date: 2018-03-21 12:08:41.551213

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '9ad9ac463bbb'
down_revision = '34454fe8fd61'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email_verified', sa.Boolean(), nullable=True))
        batch_op.add_column(
            sa.Column('email_verifier', sa.String(length=16), nullable=True)
        )
        batch_op.add_column(
            sa.Column('email_subscribed', sa.Boolean(), nullable=False, default=False)
        )
        batch_op.create_unique_constraint(None, ['email_verifier'])


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='unique')
        batch_op.drop_column('email_verifier')
        batch_op.drop_column('email_verified')
        batch_op.drop_column('email_subscribed')
