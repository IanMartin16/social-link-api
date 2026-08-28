import time
import asyncio
import logging
from typing import Any, Callable, Awaitable

logger = logging.getLogger("social-link.cache")

# timeout duro para CUALQUIER llamada a la fuente. Aunque httpx tenga su propio
# timeout, esto es el cinturón de seguridad a nivel del caché.
FETCH_TIMEOUT = 10.0


class TTLCache:
    def __init__(self):
        # value, expires_at (fresco hasta aquí)
        self._store: dict[str, tuple[Any, float]] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        # claves que tienen un refresco en background corriendo (evita lanzar N)
        self._refreshing: set[str] = set()

    def _lock_for(self, key: str) -> asyncio.Lock:
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]

    async def _do_fetch(self, key: str, fetch_fn: Callable[[], Awaitable[Any]], ttl_seconds: float) -> Any:
        """Llama a la fuente con timeout duro y guarda en caché. Devuelve el valor.
        Lanza si falla o si excede el timeout (el llamador decide qué hacer)."""
        value = await asyncio.wait_for(fetch_fn(), timeout=FETCH_TIMEOUT)
        self._store[key] = (value, time.monotonic() + ttl_seconds)
        return value

    async def _refresh_in_background(self, key, fetch_fn, ttl_seconds):
        """Refresco fuera del camino de la petición. Un solo refresco por clave."""
        if key in self._refreshing:
            return
        self._refreshing.add(key)
        try:
            async with self._lock_for(key):
                try:
                    await self._do_fetch(key, fetch_fn, ttl_seconds)
                except Exception as e:
                    # si el refresco falla, conservamos el dato viejo (no lo borramos)
                    logger.warning("cache refresh failed key=%s: %r", key, e)
        finally:
            self._refreshing.discard(key)

    async def get_or_fetch(
        self,
        key: str,
        fetch_fn: Callable[[], Awaitable[Any]],
        ttl_seconds: float,
    ) -> Any:
        now = time.monotonic()
        cached = self._store.get(key)

        # 1) HAY dato en caché
        if cached is not None:
            value, expires_at = cached
            if now < expires_at:
                # fresco -> servir directo
                return value
            # viejo -> STALE-WHILE-REVALIDATE: servir viejo YA, refrescar en background
            asyncio.create_task(self._refresh_in_background(key, fetch_fn, ttl_seconds))
            return value

        # 2) NO hay dato (arranque frío para esta clave): sí hay que esperar,
        #    pero con lock (colapsa concurrentes) y timeout duro (no cuelga).
        async with self._lock_for(key):
            # re-chequeo: otro pudo haber llenado mientras esperábamos el lock
            cached = self._store.get(key)
            if cached is not None:
                value, expires_at = cached
                if time.monotonic() < expires_at:
                    return value
            # llamada real con timeout duro; si falla, propaga (el servicio
            # ya degrada a vacío con log, como hoy)
            return await self._do_fetch(key, fetch_fn, ttl_seconds)

    def peek(self, key: str) -> Any | None:
        cached = self._store.get(key)
        if cached is None:
            return None
        value, _ = cached
        return value


cache = TTLCache()