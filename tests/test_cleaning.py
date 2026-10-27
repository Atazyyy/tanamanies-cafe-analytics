"""Unit test fungsi pembersihan data Tanamanies Cafe.

Jalankan: .venv/Scripts/python -m pytest -q
"""
import pandas as pd
import pytest

from src.clean_pipeline import (
    clean_master,
    clean_transactions,
    map_outlet,
    normalize_category,
    normalize_payment,
    normalize_status,
    normalize_text,
    parse_datetime_value,
    parse_price,
)


# ---------------------------------------------------------------- util dasar


@pytest.mark.parametrize("raw,expected", [
    ("  DAGO  ", "dago"),
    ("Tanamanies   dago", "tanamanies dago"),
    (123, "123"),
])
def test_normalize_text(raw, expected):
    assert normalize_text(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("Non-Kopi", "Non-Kopi"),
    ("non kopi", "Non-Kopi"),
    ("NONKOPI", "Non-Kopi"),
    ("  Pastry  ", "Pastry"),
    ("kopi susu", "Kopi Susu"),
])
def test_normalize_category(raw, expected):
    assert normalize_category(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    (18000, 18000.0),
    ("18000", 18000.0),
    ("18.000", 18000.0),
    ("Rp18.000", 18000.0),
    ("abc", None),
    ("", None),
])
def test_parse_price(raw, expected):
    assert parse_price(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("2026-05-12 14:23:00", pd.Timestamp("2026-05-12 14:23:00")),
    ("12/05/2026 14:23", pd.Timestamp("2026-05-12 14:23:00")),
    ("2026/05/12 14:23", pd.Timestamp("2026-05-12 14:23:00")),
    ("bukan-tanggal", pd.NaT),
])
def test_parse_datetime_value(raw, expected):
    hasil = parse_datetime_value(raw)
    if expected is pd.NaT:
        assert pd.isna(hasil)
    else:
        assert hasil == expected


@pytest.mark.parametrize("raw,expected", [
    ("QRIS", "QRIS"), ("qris", "QRIS"), ("QR", "QRIS"), ("Qris ", "QRIS"),
    ("Tunai", "Cash"), ("CASH", "Cash"),
    ("Kartu Debit", "Debit"), ("DEBIT", "Debit"),
    ("GoPay", "E-Wallet"), ("ShopeePay", "E-Wallet"), ("OVO", "E-Wallet"),
    ("", "Tidak Diketahui"),
    ("kupon-kopi", "Lainnya"),
])
def test_normalize_payment(raw, expected):
    assert normalize_payment(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("Tanamanies Dago", "OUT01"),
    ("dago", "OUT01"),
    ("BUAH BATU", "OUT02"),
    ("Tanamanies buah batu ", "OUT02"),
    ("dipatiukur", "OUT03"),
    ("jakarta", None),
    ("", None),
])
def test_map_outlet(raw, expected):
    assert map_outlet(raw) == expected


def test_normalize_status():
    assert normalize_status("") == "OK"
    assert normalize_status("ok") == "OK"
    assert normalize_status("void") == "VOID"


# ---------------------------------------------------------------- master


def test_clean_master_maps_legacy_and_typo():
    master = pd.DataFrame([
        {"product_id": "P001", "product_name": "Kopi Susu Aren", "category": "Kopi Susu", "unit_price": 18000},
        {"product_id": "P002", "product_name": "Matcha Latte", "category": "non kopi", "unit_price": "24.000"},
        {"product_id": "L002", "product_name": "kopi susu aren", "category": "kopi susu", "unit_price": 18000},
        {"product_id": "L004", "product_name": "Butter Croisant", "category": "Pastry", "unit_price": 22000},
        {"product_id": "L009", "product_name": "Es Krim Ajaib", "category": "Dessert", "unit_price": 15000},
        {"product_id": "P001", "product_name": "Kopi Susu Aren", "category": "Kopi Susu", "unit_price": 18000},  # dup
    ])
    dim, legacy_map, c = clean_master(master)
    assert len(dim) == 2
    assert set(dim["product_id"]) == {"P001", "P002"}
    assert dim.loc[dim["product_id"] == "P002", "unit_price"].item() == 24000.0
    assert legacy_map == {"L002": "P001"}   # "Butter Croisant" & "Es Krim Ajaib" tak ada padanannya di dim ini
    assert "L009" not in legacy_map          # tak ada padanan -> tidak dipetakan
    assert c["master_duplikat_id_dihapus"] == 1
    assert c["master_tidak_terpetakan"] == 2


# ---------------------------------------------------------------- transaksi


def _base_fact_rows():
    return pd.DataFrame([
        # baris normal lengkap
        {"transaction_id": "T1", "line_no": 1, "datetime": "2026-05-12 10:00:00",
         "outlet": "Tanamanies Dago", "product_id": "P001", "product_name": "Kopi Susu Aren",
         "qty": 2, "unit_price": 18000, "payment_method": "QRIS", "status": "OK"},
        # duplikat persis (ekspor ganda)
        {"transaction_id": "T1", "line_no": 1, "datetime": "2026-05-12 10:00:00",
         "outlet": "Tanamanies Dago", "product_id": "P001", "product_name": "Kopi Susu Aren",
         "qty": 2, "unit_price": 18000, "payment_method": "QRIS", "status": "OK"},
        # VOID: qty negatif
        {"transaction_id": "T2", "line_no": 1, "datetime": "12/05/2026 11:30",
         "outlet": "dago", "product_id": "P011", "product_name": "Matcha Latte",
         "qty": -1, "unit_price": 24000, "payment_method": "Tunai", "status": "VOID"},
        # ID kosong -> dipulihkan lewat nama
        {"transaction_id": "T3", "line_no": 1, "datetime": "2026/05/12 15:05",
         "outlet": "DAGO", "product_id": "", "product_name": "Matcha Latte",
         "qty": 1, "unit_price": "24.000", "payment_method": "gopay", "status": ""},
        # qty negatif tapi status kosong -> harus dipulihkan jadi VOID
        {"transaction_id": "T4", "line_no": 1, "datetime": "2026-05-12 16:00:00",
         "outlet": "Tanamanies Dago", "product_id": "P001", "product_name": "Kopi Susu Aren",
         "qty": -1, "unit_price": 18000, "payment_method": "Cash", "status": ""},
        # nama typo tanpa ID -> dipulihkan fuzzy
        {"transaction_id": "T5", "line_no": 1, "datetime": "2026-05-12 17:00:00",
         "outlet": "Tanamanies Dago", "product_id": "", "product_name": "Matcha Lette",
         "qty": 1, "unit_price": 24000, "payment_method": "QRIS", "status": "OK"},
        # outlet tidak dikenal -> dibuang
        {"transaction_id": "T6", "line_no": 1, "datetime": "2026-05-12 18:00:00",
         "outlet": "jakarta", "product_id": "P001", "product_name": "Kopi Susu Aren",
         "qty": 1, "unit_price": 18000, "payment_method": "QRIS", "status": "OK"},
    ])


@pytest.fixture()
def dim():
    return pd.DataFrame([
        {"product_id": "P001", "product_name": "Kopi Susu Aren", "category": "Kopi Susu", "unit_price": 18000.0},
        {"product_id": "P011", "product_name": "Matcha Latte", "category": "Non-Kopi", "unit_price": 24000.0},
    ])


def test_clean_transactions_full_flow(dim):
    fact, c = clean_transactions(_base_fact_rows(), dim, legacy_map={})
    # duplikat & outlet tak dikenal dibuang -> 5 baris
    assert len(fact) == 5
    assert c["duplikat_dihapus"] == 1
    assert c["outlet_tidak_dikenal_dibuang"] == 1
    assert c["id_hilang_dipulihkan_lewat_nama"] == 1
    assert c["nama_typo_dipulihkan_fuzzy"] == 1
    assert c["qty_negatif_dipulihkan_jadi_void"] == 1
    # harga teks "24.000" berhasil dikonversi
    assert fact.loc[fact["transaction_id"] == "T3", "unit_price"].item() == 24000.0
    # semua product_id teridentifikasi
    assert set(fact["product_id"]) <= {"P001", "P011"}
    # revenue hanya dari status OK (T1: 36000, T3: 24000, T5: 24000)
    ok = fact[fact["status"] == "OK"]
    assert ok["line_revenue"].sum() == 84000
    # status void/refund tersimpan, tidak ikut revenue
    assert set(fact["status"]) == {"OK", "VOID"}


def test_clean_transactions_legacy_id_mapped(dim):
    rows = _base_fact_rows()
    rows.loc[0, "product_id"] = "L002"  # ID lama dari POS outlet lain
    fact, c = clean_transactions(rows, dim, legacy_map={"L002": "P001"})
    assert (fact.loc[fact["transaction_id"] == "T1", "product_id"] == "P001").all()
    assert c["id_legacy_dipetakan"] == 1
