#!/usr/bin/env python3
"""
archive_and_prune.py — social_link: archiva a Parquet los tracks de episodios
CLOSED y los poda de la BD caliente.

DISEÑO SEGURO
  - Trabaja POR EPISODIO (una transacción por episodio): acotado y reanudable.
  - NUNCA borra sin antes: (1) escribir el Parquet, (2) releerlo y confirmar que
    el row count coincide con la BD. Si no cuadra, aborta ese episodio.
  - Dry-run por default. Solo borra con --execute.
  - Idempotente: si el Parquet del episodio ya existe y cuadra, no reexporta;
    (con --execute) procede a borrar igual. Reanudar = volver a correr.

ARCHIVA : EVENT + CENSORED   (los INVALID no valen archivo)
PODA    : EVENT + CENSORED + INVALID
DEJA    : POST_* / ACTIVE_TRENDING (abiertos) y EXCLUDED (no tienen tracks)

CREDENCIAL
  Lee la conexión de la env var SOCIAL_LINK_DB_URL (tú la pones local).
  Nunca va en el script.
    export SOCIAL_LINK_DB_URL='postgresql+psycopg://user:TU_PASS@host:port/db'

USO
  python archive_and_prune.py                 # dry-run: dice qué haría
  python archive_and_prune.py --execute       # archiva y PODA de verdad
  python archive_and_prune.py --archive-only   # solo exporta Parquet, no borra
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

ARCHIVE_LABELS = ("EVENT", "CENSORED")           # se van a Parquet
PRUNE_LABELS = ("EVENT", "CENSORED", "INVALID")  # se borran de la BD caliente
OUT_DIR = Path(os.environ.get("ARCHIVE_DIR", "archive_episode_track"))

# Columnas jsonb -> ::text para que Parquet las guarde como string estable
TRACK_SELECT = """
    SELECT track_id, episode_id, ts, price, source, in_trending,
           trend_position, rank, vol24h, drawdown_from_peak, time_in_trend_h,
           raw::text  AS raw,
           live_features::text AS live_features
    FROM episode_track
    WHERE episode_id = :eid
    ORDER BY ts
"""


def get_engine():
    url = os.environ.get("SOCIAL_LINK_DB_URL")
    if not url:
        sys.exit("ERROR: define SOCIAL_LINK_DB_URL (nunca la pongas en el script).")
    return create_engine(url)


def target_episodes(engine) -> pd.DataFrame:
    q = text(
        "SELECT episode_id, label FROM trending_episode "
        "WHERE state = 'CLOSED' AND label IN ('EVENT','CENSORED','INVALID') "
        "ORDER BY label, episode_id"
    )
    return pd.read_sql(q, engine)


def db_count(engine, eid: int) -> int:
    with engine.connect() as c:
        return c.execute(
            text("SELECT count(*) FROM episode_track WHERE episode_id = :eid"),
            {"eid": eid},
        ).scalar_one()


def parquet_path(label: str, eid: int) -> Path:
    d = OUT_DIR / f"label={label}"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"episode_{eid}.parquet"


def archive_episode(engine, eid: int, label: str) -> int:
    """Exporta el episodio a Parquet y verifica. Devuelve filas archivadas."""
    path = parquet_path(label, eid)
    expected = db_count(engine, eid)

    # idempotencia: si ya existe y cuadra, no reexportar
    if path.exists():
        existing = pd.read_parquet(path)
        if len(existing) == expected:
            return expected

    df = pd.read_sql(text(TRACK_SELECT), engine, params={"eid": eid})
    if len(df) != expected:
        raise RuntimeError(f"ep {eid}: leí {len(df)} != count {expected}")
    df.to_parquet(path, index=False)

    # verificación dura: releer y contar
    back = pd.read_parquet(path)
    if len(back) != expected:
        raise RuntimeError(f"ep {eid}: parquet {len(back)} != count {expected}")
    return expected


def delete_episode(engine, eid: int) -> int:
    with engine.begin() as c:  # transacción por episodio
        return c.execute(
            text("DELETE FROM episode_track WHERE episode_id = :eid"),
            {"eid": eid},
        ).rowcount


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true", help="archiva Y poda")
    ap.add_argument("--archive-only", action="store_true", help="solo Parquet")
    args = ap.parse_args()

    engine = get_engine()
    eps = target_episodes(engine)
    if eps.empty:
        print("No hay episodios CLOSED que procesar.")
        return

    mode = "EXECUTE (archiva + poda)" if args.execute else (
        "ARCHIVE-ONLY" if args.archive_only else "DRY-RUN (no toca nada)")
    print(f"Modo: {mode}")
    print(f"Episodios objetivo: {len(eps)}  ->  {OUT_DIR}/\n")

    archived = deleted = 0
    for _, row in eps.iterrows():
        eid, label = int(row.episode_id), row.label
        n = db_count(engine, eid)

        if not args.execute and not args.archive_only:
            tag = "archivar+podar" if label in ARCHIVE_LABELS else "podar"
            print(f"  [dry] ep {eid:>8}  {label:<9} {n:>7} tracks  -> {tag}")
            archived += n if label in ARCHIVE_LABELS else 0
            deleted += n
            continue

        if label in ARCHIVE_LABELS:
            got = archive_episode(engine, eid, label)
            archived += got
            print(f"  [arch] ep {eid:>8}  {label:<9} {got:>7} -> parquet OK")
        elif label == "INVALID":
            print(f"  [skip] ep {eid:>8}  INVALID   {n:>7} -> sin archivo")

        if args.execute:
            d = delete_episode(engine, eid)  # solo tras verificar el parquet
            deleted += d
            print(f"  [del ] ep {eid:>8}  {label:<9} {d:>7} borrados")

    print("\n--- resumen ---")
    print(f"archivados (filas): {archived:,}")
    if args.execute:
        print(f"podados    (filas): {deleted:,}")
        print("\nOJO: el DELETE deja dead tuples. Para recuperar disco del OS,")
        print("corre DESPUES (ver nota de VACUUM FULL / pg_repack).")
    elif not args.archive_only:
        print(f"se podarian (filas): {deleted:,}  (dry-run, nada borrado)")


if __name__ == "__main__":
    main()
