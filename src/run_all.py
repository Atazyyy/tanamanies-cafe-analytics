"""Orkestrator: jalankan seluruh pipeline dari nol sampai database siap.

Pemakaian:
    python -m src.run_all               # clean + build DB (pakai data mentah yang ada)
    python -m src.run_all --with-data   # generate ulang data mentah dulu
"""
from __future__ import annotations

import argparse

from src import build_db, clean_pipeline, quality_report


def main(with_data: bool = False) -> None:
    if with_data:
        from src.generate_pos_data import generate
        n = generate()
        print(f"[1/4] generate : {n:,} baris mentah")
    else:
        print("[1/4] generate : dilewati (pakai data mentah yang ada)")

    fact, dim_product, _, counters = clean_pipeline.run_pipeline()
    print(f"[2/4] cleansing: {counters['baris_masuk']:,} -> {counters['baris_keluar']:,} baris")

    stats = build_db.build_db()
    print(f"[3/4] duckdb   : {stats['fact_rows']:,} baris fact, {stats['produk']} produk")

    quality_report.write_reports(counters)
    print(f"[4/4] laporan  : docs/laporan_kualitas_data.md")
    print("Selesai. Jalankan dashboard: streamlit run dashboard/app.py")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline data Tanamanies Cafe")
    parser.add_argument("--with-data", action="store_true", help="generate ulang data mentah")
    args = parser.parse_args()
    main(with_data=args.with_data)
