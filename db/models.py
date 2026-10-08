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


from datetime import datetime
from sqlalchemy import (
    BigInteger, Integer, Numeric, Text, TIMESTAMP, Boolean,
    ForeignKey, Index, UniqueConstraint, text
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
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


# =====================================================================
# DETECTOR DE COLAPSO (pump-and-dump) — registry + episodios + serie
# Fase 0 del detector. coin_registry = semilla del ID propio de cryptolink.
# =====================================================================

class CoinRegistry(Base):
    """Semilla del ID propio. cl_id = id NATIVO estable; los ids de proveedor
    cuelgan de él (coingecko_id ahora; cmc_id / contract+chain después).
    El detector es su primer consumidor: los episodios keyean por cl_id, no symbol."""
    __tablename__ = "coin_registry"

    cl_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    coingecko_id: Mapped[str] = mapped_column(Text, nullable=False)   # id del proveedor primario
    symbol: Mapped[str | None] = mapped_column(Text)                  # display (puede colisionar: QTC/Qitcoin)
    name: Mapped[str | None] = mapped_column(Text)
    cmc_id: Mapped[str | None] = mapped_column(Text)                  # nullable (se llena cuando aplique)
    contract_addr: Mapped[str | None] = mapped_column(Text)          # ancla real futura (nullable)
    chain: Mapped[str | None] = mapped_column(Text)                   # nullable
    aliases: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"), nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False)

    episodes: Mapped[list["TrendingEpisode"]] = relationship(back_populates="coin")

    __table_args__ = (
        UniqueConstraint("coingecko_id", name="uq_registry_coingecko_id"),
        Index("ix_registry_symbol", "symbol"),
    )


class TrendingEpisode(Base):
    """Un episodio = la estancia de un coin siendo trackeado tras entrar a trending.
    Cabecera + covariables de entrada + etiqueta terminal (EVENT|CENSORED|EXCLUDED)."""
    __tablename__ = "trending_episode"

    episode_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    cl_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("coin_registry.cl_id"), nullable=False)
    coingecko_id: Mapped[str] = mapped_column(Text, nullable=False)   # denormalizado (polling rápido)
    symbol: Mapped[str | None] = mapped_column(Text)
    name: Mapped[str | None] = mapped_column(Text)

    # t0 + covariables de entrada (inputs del modelo)
    entered_trend_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)  # t0
    entry_price: Mapped[float | None] = mapped_column(Numeric)
    entry_rank: Mapped[int | None] = mapped_column(Integer)
    entry_mcap: Mapped[float | None] = mapped_column(Numeric)
    entry_vol24h: Mapped[float | None] = mapped_column(Numeric)
    entry_features: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"), nullable=False)

    # gate de aftermath (caso QTC)
    recent_high: Mapped[float | None] = mapped_column(Numeric)
    recent_high_win_d: Mapped[int] = mapped_column(Integer, server_default=text("7"), nullable=False)
    peak_confidence: Mapped[str] = mapped_column(Text, server_default=text("'observed'"), nullable=False)  # observed|inferred|unknown

    # pico/fondo rolling
    peak_price: Mapped[float | None] = mapped_column(Numeric)
    peak_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    trough_price: Mapped[float | None] = mapped_column(Numeric)
    trough_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    max_drawdown: Mapped[float | None] = mapped_column(Numeric)       # 0..1

    # ciclo de vida
    left_trend_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    state: Mapped[str] = mapped_column(Text, server_default=text("'ACTIVE_TRENDING'"), nullable=False)
                                       # ACTIVE_TRENDING|POST_INTENSIVE|POST_LIGHT|CLOSED
    label: Mapped[str | None] = mapped_column(Text)                   # EVENT|CENSORED|EXCLUDED
    event_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    time_to_event_h: Mapped[float | None] = mapped_column(Numeric)    # TARGET de supervivencia
    dump_speed_h: Mapped[float | None] = mapped_column(Numeric)       # FEATURE (no etiqueta)
    closed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False)

    coin: Mapped["CoinRegistry"] = relationship(back_populates="episodes")
    tracks: Mapped[list["EpisodeTrack"]] = relationship(back_populates="episode", cascade="all, delete-orphan")

    __table_args__ = (
        # un episodio ABIERTO por coin → la reentrada CONTINÚA el mismo (constraint de DB)
        Index("uq_episode_open_coin", "cl_id", unique=True, postgresql_where=text("state <> 'CLOSED'")),
        Index("ix_episode_open", "state", postgresql_where=text("state <> 'CLOSED'")),
        Index("ix_episode_cl", "cl_id", "entered_trend_at"),
    )


class EpisodeTrack(Base):
    """Serie temporal del episodio. raw = CRUDOS (guardar raw, derivar después);
    live_features = covariables tiempo-dependientes (recalculables desde raw)."""
    __tablename__ = "episode_track"

    track_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    episode_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("trending_episode.episode_id", ondelete="CASCADE"), nullable=False
    )
    ts: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    price: Mapped[float | None] = mapped_column(Numeric)
    source: Mapped[str] = mapped_column(Text, server_default=text("'coingecko'"), nullable=False)  # coingecko|cmc
    in_trending: Mapped[bool | None] = mapped_column(Boolean)
    trend_position: Mapped[int | None] = mapped_column(Integer)
    rank: Mapped[int | None] = mapped_column(Integer)
    vol24h: Mapped[float | None] = mapped_column(Numeric)
    drawdown_from_peak: Mapped[float | None] = mapped_column(Numeric)
    time_in_trend_h: Mapped[float | None] = mapped_column(Numeric)
    raw: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"), nullable=False)
    live_features: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"), nullable=False)

    episode: Mapped["TrendingEpisode"] = relationship(back_populates="tracks")

    __table_args__ = (
        # único por (episodio, ts); su índice también sirve para lookups ordenados
        UniqueConstraint("episode_id", "ts", name="uq_track_ep_ts"),
    )
