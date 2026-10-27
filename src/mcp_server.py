"""MCP server Tanamanies Cafe Analytics.

Memungkinkan AI assistant (Claude Code, dsb.) menjawab pertanyaan bisnis
dengan meng-query database DuckDB yang sudah dibersihkan — contoh nyata
"connector data agar setiap divisi bisa mengakses data melalui AI".

Konfigurasi Claude Code (.mcp.json di root project):

    {
      "mcpServers": {
        "tanamanies-analytics": {
          "command": ".venv/Scripts/python.exe",
          "args": ["-m", "src.mcp_server"]
        }
      }
    }

Keamanan: tool `jalankan_sql` hanya menerima SELECT/WITH, hasil dibatasi
200 baris, dan database dibuka read-only.
"""
from __future__ import annotations

import re

import duckdb
import pandas as pd

from src.config import DB_PATH, PROCESSED_DIR

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Paket 'mcp' belum terpasang. Jalankan: pip install -r requirements.txt"
    ) from exc

mcp = FastMCP("tanamanies-analytics")


def _con() -> duckdb.DuckDBPyConnection:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            "Database belum dibangun. Jalankan: python -m src.run_all --with-data"
        )
    return duckdb.connect(str(DB_PATH), read_only=True)


def _to_str(df: pd.DataFrame) -> str:
    if df.empty:
        return "(tidak ada data)"
    return df.to_string(index=False)


@mcp.tool()
def ringkasan_periode(start_date: str, end_date: str, outlet: str = "semua") -> str:
    """Ringkasan performa (omzet, transaksi, item, rata-rata belanja) per periode.

    Args:
        start_date: tanggal mulai format YYYY-MM-DD
        end_date: tanggal akhir format YYYY-MM-DD (inklusif)
        outlet: 'semua' atau nama area outlet (dago / buah batu / dipatiukur)
    """
    con = _con()
    q = """
    SELECT SUM(pendapatan) AS omzet, SUM(jumlah_transaksi) AS transaksi,
           SUM(item_terjual) AS item, SUM(pendapatan)/SUM(jumlah_transaksi) AS rata_belanja
    FROM v_daily_revenue
    WHERE date BETWEEN ? AND ?
    """
    params: list = [start_date, end_date]
    if outlet.lower() != "semua":
        q += " AND lower(outlet_name) LIKE ?"
        params.append(f"%{outlet.lower()}%")
    df = con.execute(q, params).df()
    con.close()
    return _to_str(df)


@mcp.tool()
def penjualan_harian(start_date: str, end_date: str) -> str:
    """Omzet harian seluruh outlet untuk rentang tanggal tertentu (YYYY-MM-DD)."""
    con = _con()
    df = con.execute(
        """SELECT date, outlet_name, jumlah_transaksi, item_terjual, pendapatan
           FROM v_daily_revenue WHERE date BETWEEN ? AND ?
           ORDER BY date, outlet_name""",
        [start_date, end_date],
    ).df()
    con.close()
    return _to_str(df)


@mcp.tool()
def top_produk(start_date: str, end_date: str, n: int = 10, kategori: str = "semua") -> str:
    """Produk terlaris berdasarkan qty pada periode tertentu.

    Args:
        start_date, end_date: format YYYY-MM-DD
        n: jumlah produk yang ditampilkan (maks 30)
        kategori: 'semua' atau salah satu dari Kopi Susu / Kopi Hitam / Non-Kopi / Signature / Pastry / Snack
    """
    n = max(1, min(n, 30))
    con = _con()
    q = """
    SELECT p.product_name, p.category, SUM(f.qty) AS qty_terjual, SUM(f.line_revenue) AS pendapatan
    FROM fact_sales f JOIN dim_product p USING (product_id)
    WHERE f.status = 'OK' AND f.date BETWEEN ? AND ?
    """
    params: list = [start_date, end_date]
    if kategori.lower() != "semua":
        q += " AND lower(p.category) = ?"
        params.append(kategori.lower())
    q += " GROUP BY 1, 2 ORDER BY qty_terjual DESC LIMIT " + str(n)
    df = con.execute(q, params).df()
    con.close()
    return _to_str(df)


@mcp.tool()
def jalankan_sql(query: str) -> str:
    """Jalankan query SQL analitik read-only pada database Tanamanies Cafe.

    Hanya menerima query SELECT atau WITH. Tabel yang tersedia:
    fact_sales, dim_product, dim_outlet, serta view:
    v_daily_revenue, v_outlet_summary, v_product_performance,
    v_payment_mix, v_hourly_pattern, v_category_revenue.
    """
    q = query.strip().rstrip(";")
    if not re.match(r"(?is)^(select|with)\b", q):
        return "Ditolak: hanya query SELECT/WITH yang diizinkan."
    try:
        con = _con()
        df = con.execute(f"SELECT * FROM ({q}) AS _sub LIMIT 200").df()
        con.close()
        return _to_str(df)
    except Exception as exc:  # noqa: BLE001 — kirim error SQL ke assistant, bukan crash
        return f"Query gagal: {exc}"


if __name__ == "__main__":
    mcp.run()
