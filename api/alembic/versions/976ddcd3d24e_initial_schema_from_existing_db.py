"""initial_schema_from_existing_db

Revision ID: 976ddcd3d24e
Revises: 
Create Date: 2026-04-01 19:56:54.434098

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '976ddcd3d24e'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Initial schema — already exists in DB. Stamp only, do not run.

    This migration represents the baseline schema created from pos_database_schema.sql.
    Run: alembic stamp head (to mark this as applied without executing)
    """
    pass


def downgrade() -> None:
    """Downgrade would drop all tables — intentionally left empty for safety."""
    pass
