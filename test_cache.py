import asyncio
import time
from utils.cache import TTLCache


async def slow_fetch():
    await asyncio.sleep(30)   # fuente lenta
    return "FRESH"


async def fast_fetch():
    return "FRESH"


async def test_timeout_duro():
    """Arranque frío con fuente lenta: debe cortar por FETCH_TIMEOUT, no colgar."""
    c = TTLCache()
    t0 = time.monotonic()
    try:
        await c.get_or_fetch("k", slow_fetch, ttl_seconds=60)
        print("FAIL: no debería haber devuelto (fetch tarda 30s)")
    except asyncio.TimeoutError:
        dt = time.monotonic() - t0
        # debe cortar cerca de FETCH_TIMEOUT (10s), NO a los 30s
        assert dt < 12, f"cortó tarde: {dt:.1f}s"
        print(f"OK timeout duro: cortó a los {dt:.1f}s (no 30s)")


async def test_stale_while_revalidate():
    """Con dato viejo, servir el viejo AL INSTANTE aunque el refresh sea lento."""
    c = TTLCache()
    # 1) llenar con dato fresco y TTL corto
    await c.get_or_fetch("k", fast_fetch, ttl_seconds=1)
    # 2) esperar a que expire
    await asyncio.sleep(1.1)
    # 3) ahora el fetch es LENTO. Pedir de nuevo: debe devolver el viejo YA,
    #    no esperar los 30s del refresh.
    c2_fetch = slow_fetch
    t0 = time.monotonic()
    val = await c.get_or_fetch("k", c2_fetch, ttl_seconds=1)
    dt = time.monotonic() - t0
    assert val == "FRESH", f"esperaba dato viejo 'FRESH', got {val!r}"
    assert dt < 0.5, f"NO sirvió al instante, tardó {dt:.1f}s (colgó en el refresh)"
    print(f"OK stale-while-revalidate: sirvió dato viejo en {dt*1000:.0f}ms (refresh en background)")


async def test_colapsa_concurrentes():
    """N peticiones concurrentes en frío -> UNA sola llamada a la fuente."""
    c = TTLCache()
    calls = {"n": 0}

    async def counting_fetch():
        calls["n"] += 1
        await asyncio.sleep(0.2)
        return "V"

    # 10 peticiones a la vez sobre la misma clave
    results = await asyncio.gather(*[
        c.get_or_fetch("k", counting_fetch, ttl_seconds=60) for _ in range(10)
    ])
    assert all(r == "V" for r in results)
    assert calls["n"] == 1, f"esperaba 1 llamada, hubo {calls['n']}"
    print(f"OK colapsa concurrentes: 10 peticiones -> {calls['n']} llamada")


async def main():
    await test_timeout_duro()
    await test_stale_while_revalidate()
    await test_colapsa_concurrentes()
    print("\nTODAS LAS PRUEBAS PASARON — el caché es seguro para desplegar")


if __name__ == "__main__":
    asyncio.run(main())