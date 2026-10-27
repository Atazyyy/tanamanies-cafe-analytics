"""Konfigurasi terpusat Tanamanies Cafe Analytics.

Tanamanies Cafe adalah brand fiktif kedai kopi di Bandung. Seluruh data
pada project ini adalah data simulasi, bukan data bisnis nyata.
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
SAMPLE_DIR = DATA_DIR / "sample"
DOCS_DIR = BASE_DIR / "docs"
DB_PATH = DATA_DIR / "tanamanies.duckdb"

# Periode simulasi: 6 bulan penuh
DATA_START = "2026-04-01"
DATA_END = "2026-09-30"

OUTLETS = [
    {"outlet_id": "OUT01", "name": "Tanamanies Dago", "area": "Dago", "daily_tx_base": 150},
    {"outlet_id": "OUT02", "name": "Tanamanies Buah Batu", "area": "Buah Batu", "daily_tx_base": 110},
    {"outlet_id": "OUT03", "name": "Tanamanies Dipatiukur", "area": "Dipatiukur", "daily_tx_base": 90},
]
