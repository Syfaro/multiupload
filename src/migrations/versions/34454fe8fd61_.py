"""update user

Revision ID: 34454fe8fd61
Revises: da88034f27d3
Create Date: 2018-03-21 11:08:54.326428

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '34454fe8fd61'
down_revision = 'da88034f27d3'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user', sa.Column('email', sa.String(length=254), nullable=True))
    op.create_unique_constraint(None, 'user', ['email'])
    op.drop_column('user', 'dark_theme')


def downgrade():
    op.add_column('user', sa.Column('dark_theme', sa.BOOLEAN(), nullable=True))
    op.drop_constraint(None, 'user', type_='unique')
    op.drop_column('user', 'email')
