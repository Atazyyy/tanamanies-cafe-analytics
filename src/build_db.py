"""Bangun database DuckDB dari parquet hasil cleansing + view analitik.

File DB dibangun ulang dari nol setiap kali pipeline dijalankan agar angka
selalu konsisten dengan data mentah terbaru.
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from src.config import DB_PATH, PROCESSED_DIR
from src.clean_pipeline import run_pipeline

VIEWS_SQL = Path(__file__).resolve().parent.parent / "sql" / "views.sql"


def build_db() -> dict:
    fact_df = pd.read_parquet(PROCESSED_DIR / "fact_sales.parquet")
    product_df = pd.read_parquet(PROCESSED_DIR / "dim_product.parquet")
    outlet_df = pd.read_parquet(PROCESSED_DIR / "dim_outlet.parquet")

    DB_PATH.unlink(missing_ok=True)
    con = duckdb.connect(str(DB_PATH))
    con.execute("CREATE TABLE fact_sales AS SELECT * FROM fact_df")
    con.execute("CREATE TABLE dim_product AS SELECT * FROM product_df")
    con.execute("CREATE TABLE dim_outlet AS SELECT * FROM outlet_df")
    con.execute(VIEWS_SQL.read_text(encoding="utf-8"))

    stats = {
        "fact_rows": con.execute("SELECT COUNT(*) FROM fact_sales").fetchone()[0],
        "produk": con.execute("SELECT COUNT(*) FROM dim_product").fetchone()[0],
        "outlet": con.execute("SELECT COUNT(*) FROM dim_outlet").fetchone()[0],
        "pendapatan_total": con.execute(
            "SELECT SUM(line_revenue) FROM fact_sales WHERE status = 'OK'"
        ).fetchone()[0],
    }
    con.close()
    return stats


if __name__ == "__main__":
    run_pipeline()  # pastikan parquet terbaru
    stats = build_db()
    print(f"[build_db] fact_sales   : {stats['fact_rows']:,} baris")
    print(f"[build_db] dim_product  : {stats['produk']}")
    print(f"[build_db] dim_outlet   : {stats['outlet']}")
    print(f"[build_db] omzet 6 bln  : Rp{stats['pendapatan_total']:,.0f}".replace(",", "."))
    print(f"[build_db] database     : {DB_PATH}")
