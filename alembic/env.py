"""
alembic/env.py — configurado para modelos async de social_link.

Reemplaza el env.py que genera `alembic init -t async alembic` con este.
Cambios clave respecto a la plantilla:
  - Toma la URL de tu db.session (misma normalización postgresql+asyncpg).
  - Apunta target_metadata a Base.metadata de tus modelos (para autogenerate).
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# --- IMPORTA TUS MODELOS Y LA URL --------------------------------------------
# Importar los modelos registra las tablas en Base.metadata (necesario para
# --autogenerate). Importa el módulo de modelos completo para que todas las
# clases queden registradas.
from db.session import DATABASE_URL          # ya normalizada a postgresql+asyncpg
from db.models import Base                    # tu DeclarativeBase
import db.models  # noqa: F401  (asegura que Snapshot/AssetSnapshot/TrendingSnapshot se registren)
# ------------------------------------------------------------------------------

config = context.config

# Inyecta la URL desde el entorno (no la dejes hardcodeada en alembic.ini)
config.set_main_option("sqlalchemy.url", DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Migraciones en modo 'offline' (genera SQL sin conectar)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,        # detecta cambios de tipo de columna
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,        # detecta cambios de tipo en autogenerate
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Crea un engine async y corre las migraciones dentro de él."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
