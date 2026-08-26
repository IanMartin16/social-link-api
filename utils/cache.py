"""
Caché simple en memoria con TTL para social_link.

Motivación: hoy cada fetch_* pega directo a CoinGecko sin caché → N requests del
portal = N llamadas (mismo patrón N×N que se peleó en el hardening del Java/Vercel).
Este caché:
  - Reduce las llamadas del portal (una llamada por TTL sirve a todos los visitantes).
  - Permite que el JOB de persistencia lea del MISMO caché → cero llamadas extra.

No necesita Redis: un dict en memoria basta (como el PriceCache del Java). Si algún
día social_link escala a múltiples instancias, se migra a Redis compartido.
"""

import time
from typing import Any, Callable, Awaitable
import asyncio


class TTLCache:
    def __init__(self):
        self._store: dict[str, tuple[float, Any]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock_for(self, key: str) -> asyncio.Lock:
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]

    async def get_or_fetch(
        self,
        key: str,
        fetch_fn: Callable[[], Awaitable[Any]],
        ttl_seconds: float,
    ) -> Any:
        """Devuelve el valor cacheado si está fresco; si no, llama fetch_fn una vez.

        El lock por clave evita que múltiples requests concurrentes disparen
        llamadas simultáneas a CoinGecko para la misma clave (stampede).
        """
        now = time.monotonic()
        cached = self._store.get(key)
        if cached is not None:
            expires_at, value = cached
            if now < expires_at:
                return value

        # dato viejo o ausente → una sola llamada protegida por lock
        async with self._lock_for(key):
            # re-chequeo: otro request pudo haber refrescado mientras esperábamos
            now = time.monotonic()
            cached = self._store.get(key)
            if cached is not None:
                expires_at, value = cached
                if now < expires_at:
                    return value

            value = await fetch_fn()
            self._store[key] = (now + ttl_seconds, value)
            return value

    def peek(self, key: str) -> Any | None:
        """Devuelve el valor cacheado SIN llamar a la fuente (aunque esté viejo).
        Útil para el job: si hay algo, lo persiste; nunca dispara una llamada."""
        cached = self._store.get(key)
        if cached is None:
            return None
        _, value = cached
        return value


# instancia global compartida por el proceso (portal + job leen de aquí)
cache = TTLCache()
