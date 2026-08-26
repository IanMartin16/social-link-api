"""
Modelos SQLAlchemy 2.0 (async) para la persistencia de social_link.
Primera BD del servicio (nació stateless). Postgres en Railway.

Traducción del DDL a ORM. Alembic lee estos modelos para generar migraciones.
"""

from datetime import datetime
from sqlalchemy import (
    BigInteger, Integer, Numeric, Text, TIMESTAMP, ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Snapshot(Base):
    """Cabezal global por captura: estado del mercado en un instante."""
    __tablename__ = "snapshot"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    captured_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    # backdrop (fear & greed)
    fng_value: Mapped[int | None] = mapped_column(Integer)
    fng_label: Mapped[str | None] = mapped_column(Text)

    # contexto global del basic-signals
    coverage: Mapped[str | None] = mapped_column(Text)
    market_tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text))

    # trazabilidad
    source_markets: Mapped[str | None] = mapped_column(Text)
    source_signals: Mapped[str | None] = mapped_column(Text)

    assets: Mapped[list["AssetSnapshot"]] = relationship(back_populates="snapshot")
    trending: Mapped[list["TrendingSnapshot"]] = relationship(back_populates="snapshot")

    __table_args__ = (
        Index("idx_snapshot_captured_at", "captured_at"),
    )


class AssetSnapshot(Base):
    """Por símbolo: la señal REAL del markets payload. Tabla central para el ML."""
    __tablename__ = "asset_snapshot"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("snapshot.id"), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    symbol: Mapped[str] = mapped_column(Text, nullable=False)

    # precio + contexto real (señales NO circulares)
    price: Mapped[float | None] = mapped_column(Numeric)
    change_24h: Mapped[float | None] = mapped_column(Numeric)
    high_24h: Mapped[float | None] = mapped_column(Numeric)
    low_24h: Mapped[float | None] = mapped_column(Numeric)
    market_cap: Mapped[float | None] = mapped_column(Numeric)
    volume_24h: Mapped[float | None] = mapped_column(Numeric)   # señal estrella
    rank: Mapped[int | None] = mapped_column(Integer)
    ath: Mapped[float | None] = mapped_column(Numeric)
    ath_change_pct: Mapped[float | None] = mapped_column(Numeric)
    circulating_supply: Mapped[float | None] = mapped_column(Numeric)
    total_supply: Mapped[float | None] = mapped_column(Numeric)
    max_supply: Mapped[float | None] = mapped_column(Numeric)

    snapshot: Mapped["Snapshot"] = relationship(back_populates="assets")

    __table_args__ = (
        Index("idx_asset_snapshot_symbol_time", "symbol", "captured_at"),
        Index("idx_asset_snapshot_time", "captured_at"),
    )


class TrendingSnapshot(Base):
    """Atención REAL: qué busca la gente (endpoint /search/trending).
    Incluye no-top y shitcoins a propósito: su aparición ES la señal."""
    __tablename__ = "trending_snapshot"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("snapshot.id"))
    captured_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    position: Mapped[int | None] = mapped_column(Integer)          # orden en la lista (0..N)
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str | None] = mapped_column(Text)
    coin_id: Mapped[str | None] = mapped_column(Text)             # el "id" de coingecko (ej "polyswarm")
    market_cap_rank: Mapped[int | None] = mapped_column(Integer)   # null/alto si no-top
    score: Mapped[int | None] = mapped_column(Integer)            # el "score" del trending
    price_usd: Mapped[float | None] = mapped_column(Numeric)       # data.price
    price_change_24h_usd: Mapped[float | None] = mapped_column(Numeric)  # data.price_change_percentage_24h["usd"]
    market_cap_usd: Mapped[float | None] = mapped_column(Numeric)  # parseado de "$40,179,689"
    total_volume_usd: Mapped[float | None] = mapped_column(Numeric) # parseado de "$122,333,736"

    snapshot: Mapped["Snapshot"] = relationship(back_populates="trending")

    __table_args__ = (
        Index("idx_trending_symbol_time", "symbol", "captured_at"),
        Index("idx_trending_time", "captured_at"),
    )