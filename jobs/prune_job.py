# jobs/prune_job.py — retención de social_link (todas las podas juntas)
from sqlalchemy import text
from db.session import get_session

async def prune_asset_snapshot(days: int = 90) -> int:
    async with get_session() as session:
        res = await session.execute(text(
            "DELETE FROM asset_snapshot WHERE captured_at < now() - (:days || ' days')::interval"
        ), {"days": days})
        await session.commit()
        print(f"[prune] asset_snapshot: {res.rowcount} filas (> {days}d)")
        return res.rowcount
