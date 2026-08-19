"""crear_tabla_usuarios

Revision ID: a1b2c3d4e5f6
Revises: 31a398d3b433
Create Date: 2026-08-19

Crea la tabla de usuarios (id UUID, alineada con core.models.Usuario).
Incluye 'activo' y 'debe_cambiar_password'.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '31a398d3b433'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'usuarios',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('username', sa.String(length=64), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('activo', sa.Boolean(),
                  server_default=sa.text('true'), nullable=False),
        sa.Column('debe_cambiar_password', sa.Boolean(),
                  server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
    )
    op.create_index(op.f('ix_usuarios_username'), 'usuarios', ['username'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_usuarios_username'), table_name='usuarios')
    op.drop_table('usuarios')