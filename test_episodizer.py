import asyncio
from db.session import get_session
from detector.episodizer import run_episodizer   # tu ruta ya ajustada

async def main():
    async with get_session() as s:
        print(await run_episodizer(s))

asyncio.run(main())