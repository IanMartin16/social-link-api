"""
Resolver de id estable para el detector (Fase 0.2).

symbol/trending-row -> coingecko_id (ESTABLE) -> cl_id (ID propio).

Regla dura (lección QTC/Qitcoin): NUNCA se keyea por symbol. Si no hay un
coingecko_id confiable, el resolver NO inventa: regresa None y el episodizador
salta ese símbolo (dato equivocado es peor que sin dato).

Ubicación sugerida: junto a tu código del detector (p.ej. detector/resolver.py).
Ajusta el import de CoinRegistry a tu layout real.
"""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import CoinRegistry  


async def resolve_cl_id(
    session: AsyncSession,
    *,
    coingecko_id: str | None,
    symbol: str | None = None,
    name: str | None = None,
) -> int | None:
    """
    Devuelve el cl_id del coin, creándolo en coin_registry si no existe.

    - Keyea por coingecko_id (único, estable). Upsert atómico: a prueba de la
      carrera de dos inserciones concurrentes (el UNIQUE lo protege, el
      ON CONFLICT lo resuelve limpio).
    - Enriquece symbol/name solo si llega un valor no nulo (coalesce: no pisa
      con NULL lo que ya había).
    - Sin coingecko_id -> None (no se resuelve por symbol, colisiona).

    El caller hace commit; aquí solo se emite el statement (devuelve el cl_id
    vía RETURNING, sin necesidad de flush/refresh extra).
    """
    if not coingecko_id:
        return None

    cg_id = coingecko_id.strip().lower()
    sym = symbol.strip().upper() if symbol else None
    nm = name.strip() if name else None

    stmt = pg_insert(CoinRegistry).values(
        coingecko_id=cg_id,
        symbol=sym,
        name=nm,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["coingecko_id"],      # usa uq_registry_coingecko_id
        set_=dict(
            symbol=func.coalesce(stmt.excluded.symbol, CoinRegistry.symbol),
            name=func.coalesce(stmt.excluded.name, CoinRegistry.name),
            updated_at=func.now(),
        ),
    ).returning(CoinRegistry.cl_id)

    cl_id = await session.scalar(stmt)
    return cl_id
