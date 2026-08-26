"""
db/session.py — engine async y fábrica de sesiones para social_link.

Sirve a los dos entornos con la MISMA URL de env:
  - local:   postgresql+asyncpg://social_link:local_dev_pw@localhost:5432/social_link
  - Railway: (inyecta DATABASE_URL como postgresql://... → se normaliza abajo)

Uso:
    from db.session import get_session, engine

    async with get_session() as session:
        session.add(row)
        await session.commit()
"""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def _normalize_db_url(raw: str) -> str:
    """Railway entrega DATABASE_URL como 'postgresql://...' (driver síncrono).
    SQLAlchemy async necesita el driver asyncpg → forzamos el prefijo.
    También acepta 'postgres://' (algunos proveedores lo usan)."""
    if raw.startswith("postgresql+asyncpg://"):
        return raw
    if raw.startswith("postgresql://"):
        return raw.replace("postgresql://", "postgresql+asyncpg://", 1)
    if raw.startswith("postgres://"):
        return raw.replace("postgres://", "postgresql+asyncpg://", 1)
    return raw


DATABASE_URL = _normalize_db_url(
    os.environ.get("DATABASE_URL", "")
)

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL no está definida. En local, apunta al Postgres de Docker; "
        "en Railway se inyecta al vincular el servicio Postgres."
    )


# Pool conservador: Railway tiene límites de conexiones, y este servicio no
# necesita muchas (una API de lectura + un job cada 10 min).
engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=False,             # True temporalmente si quieres ver el SQL en local
    pool_size=5,
    max_overflow=5,
    pool_pre_ping=True,     # evita usar conexiones muertas (Railway las recicla)
    pool_recycle=1800,      # recicla conexiones cada 30 min
)

SessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,   # los objetos siguen usables tras commit
)


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """Context manager para una sesión. Hace rollback si algo truena."""
    session = SessionFactory()
    try:
        yield session
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
