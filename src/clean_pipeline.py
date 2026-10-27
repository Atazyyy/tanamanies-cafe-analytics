"""Pipeline pembersihan data POS Tanamanies Cafe.

Tahapan:
1.  Baca semua ekspor CSV mentah + master produk
2.  Bersihkan master -> dim_product + peta ID legacy -> ID kanonik
3.  Bersihkan transaksi: tanggal, outlet, harga, qty, status, metode bayar
4.  Pulihkan product_id yang hilang/tidak dikenal lewat nama (exact lalu fuzzy)
5.  Hapus duplikat, hitung statistik kualitas, tulis parquet + JSON counter

Setiap langkah mencatat jumlah baris yang diperbaiki/dibuang agar seluruh
proses dapat diaudit (laporan kualitas data).
"""
from __future__ import annotations

import difflib
import json
import re
from datetime import datetime

import pandas as pd

from src.config import OUTLETS, PROCESSED_DIR, RAW_DIR

# ---------------------------------------------------------------- util dasar


def normalize_text(v) -> str:
    """Lowercase, rapikan spasi berlebih -> kunci pembanding yang konsisten."""
    return re.sub(r"\s+", " ", str(v).strip().lower())


def normalize_category(v) -> str | None:
    """'non kopi' / 'NONKOPI' / 'Non-Kopi' -> 'Non-Kopi' (kanonik menu)."""
    canon = ["Kopi Susu", "Kopi Hitam", "Non-Kopi", "Signature", "Pastry", "Snack"]
    key = re.sub(r"[\s\-_]+", "", normalize_text(v))
    for c in canon:
        if key == re.sub(r"[\s\-_]+", "", normalize_text(c)):
            return c
    return None


def parse_price(v) -> float | None:
    """Terima 18000, '18.000', 'Rp18.000' -> 18000.0. None jika rusak."""
    s = str(v).strip().lower().replace("rp", "").strip()
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")  # titik sebagai pemisah ribuan gaya Indonesia
    try:
        return float(s)
    except ValueError:
        return None


def parse_datetime_value(v):
    """Parse satu nilai datetime dari 3 format ekspor POS yang berbeda."""
    s = str(v).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M", "%Y/%m/%d %H:%M"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return pd.NaT


PAYMENT_RULES = [
    ("qr", "QRIS"),
    ("tunai", "Cash"), ("cash", "Cash"),
    ("debit", "Debit"), ("kartu", "Debit"),
    ("ovo", "E-Wallet"), ("gopay", "E-Wallet"), ("shopeepay", "E-Wallet"),
    ("e-wallet", "E-Wallet"), ("ewallet", "E-Wallet"),
]


def normalize_payment(v) -> str:
    """Satukan 16+ sebutan metode bayar menjadi 4 kanonik + Lainnya."""
    k = normalize_text(v)
    if not k:
        return "Tidak Diketahui"
    for needle, canon in PAYMENT_RULES:
        if needle in k:
            return canon
    return "Lainnya"


OUTLET_KEYWORDS = [("dago", "OUT01"), ("buah batu", "OUT02"), ("dipatiukur", "OUT03")]


def map_outlet(v) -> str | None:
    """'DAGO' / 'dago' / 'Tanamanies dago ' -> outlet_id, None jika tak dikenal."""
    k = normalize_text(v)
    for kw, oid in OUTLET_KEYWORDS:
        if kw in k:
            return oid
    return None


def normalize_status(v) -> str:
    k = normalize_text(v)
    if k in ("", "ok", "normal", "success"):
        return "OK"
    return k.upper()


# ---------------------------------------------------------------- master


def clean_master(master: pd.DataFrame):
    """Master kotor -> dim_product + peta legacy_id -> product_id kanonik.

    Duplikat master disatukan lewat nama ternormalisasi; nama yang tidak
    persis sama (typo) dicocokkan dengan difflib (fuzzy matching).
    """
    counters = {"master_baris_masuk": len(master), "master_duplikat_id_dihapus": 0,
                "master_legacy_dipetakan": 0, "master_tidak_terpetakan": 0}
    m = master.copy()
    m["name_norm"] = m["product_name"].map(normalize_text)
    m["price_clean"] = m["unit_price"].map(parse_price)
    m["category_clean"] = m["category"].map(normalize_category)

    dup = m.duplicated(subset=["product_id"], keep="first")
    counters["master_duplikat_id_dihapus"] = int(dup.sum())
    m = m[~dup]

    is_canonical = m["product_id"].str.upper().str.startswith("P")
    dim = m[is_canonical][["product_id", "product_name", "category_clean", "price_clean"]]
    dim = dim.rename(columns={"category_clean": "category", "price_clean": "unit_price"})
    dim = dim.sort_values("product_id").reset_index(drop=True)

    name_to_id = {normalize_text(r.product_name): r.product_id for r in dim.itertuples()}
    canon_names = list(name_to_id)
    legacy_map: dict[str, str] = {}
    for row in m[~is_canonical].itertuples():
        target = name_to_id.get(row.name_norm)
        if target is None:
            close = difflib.get_close_matches(row.name_norm, canon_names, n=1, cutoff=0.8)
            target = name_to_id[close[0]] if close else None
        if target:
            legacy_map[row.product_id] = target
            counters["master_legacy_dipetakan"] += 1
        else:
            counters["master_tidak_terpetakan"] += 1
    return dim, legacy_map, counters


# ---------------------------------------------------------------- transaksi


def clean_transactions(df: pd.DataFrame, dim: pd.DataFrame, legacy_map: dict):
    """Bersihkan seluruh baris transaksi mentah -> fact_sales siap analisis."""
    c = {"baris_masuk": len(df)}
    t = df.copy()

    # 1. Datetime: 3 format campur -> satu tipe; buang yang benar-benar rusak
    t["datetime"] = t["datetime"].map(parse_datetime_value)
    n_nat = int(t["datetime"].isna().sum())
    t = t.dropna(subset=["datetime"])
    c["tanggal_format_campur_dibersihkan"] = c["baris_masuk"] - n_nat
    c["tanggal_rusak_dibuang"] = n_nat
    t["date"] = t["datetime"].dt.date

    # 2. Outlet tidak konsisten -> outlet_id
    t["outlet_id"] = t["outlet"].map(map_outlet)
    c["outlet_tidak_dikenal_dibuang"] = int(t["outlet_id"].isna().sum())
    t = t.dropna(subset=["outlet_id"])

    # 3. Harga teks berformat -> angka; qty -> numerik
    t["unit_price"] = t["unit_price"].map(parse_price)
    c["harga_rusak_dibuang"] = int(t["unit_price"].isna().sum())
    t = t.dropna(subset=["unit_price"])
    t["qty"] = pd.to_numeric(t["qty"], errors="coerce")
    t = t.dropna(subset=["qty"])
    t["qty"] = t["qty"].astype(int)

    # 4. Status: kosongkan/normalisasi; qty negatif tanpa status -> VOID
    t["status"] = t["status"].map(normalize_status)
    mask_anomali = (t["qty"] < 0) & (t["status"] == "OK")
    c["qty_negatif_dipulihkan_jadi_void"] = int(mask_anomali.sum())
    t.loc[mask_anomali, "status"] = "VOID"

    # 5. Duplikat ekspor -> simpan satu
    dup = t.duplicated(subset=["transaction_id", "line_no"], keep="first")
    c["duplikat_dihapus"] = int(dup.sum())
    t = t[~dup]

    # 6. Pulihkan product_id: kanonik -> legacy -> nama exact -> fuzzy
    t["product_id"] = t["product_id"].astype(str).str.strip()
    name_to_id = {normalize_text(r.product_name): r.product_id for r in dim.itertuples()}
    canon_names = list(name_to_id)

    in_canon = t["product_id"].isin(dim["product_id"])
    in_legacy = (~in_canon) & t["product_id"].isin(legacy_map)
    t["product_resolved"] = t["product_id"]
    t.loc[in_legacy, "product_resolved"] = t.loc[in_legacy, "product_id"].map(legacy_map)
    c["id_legacy_dipetakan"] = int(in_legacy.sum())

    need_name = ~in_canon & ~in_legacy
    resolved_by_name = need_name & t["product_name"].map(
        lambda n: normalize_text(n) in name_to_id
    )
    t.loc[resolved_by_name, "product_resolved"] = t.loc[resolved_by_name, "product_name"].map(
        lambda n: name_to_id[normalize_text(n)]
    )
    c["id_hilang_dipulihkan_lewat_nama"] = int(resolved_by_name.sum())

    still_missing = need_name & ~resolved_by_name
    if still_missing.any():
        unmatched_norms = t.loc[still_missing, "product_name"].map(normalize_text).unique()
        typo_map = {}
        for norm in unmatched_norms:
            close = difflib.get_close_matches(norm, canon_names, n=1, cutoff=0.8)
            if close:
                typo_map[norm] = name_to_id[close[0]]
        by_typo = still_missing & t["product_name"].map(lambda n: normalize_text(n) in typo_map)
        t.loc[by_typo, "product_resolved"] = t.loc[by_typo, "product_name"].map(
            lambda n: typo_map[normalize_text(n)]
        )
        c["nama_typo_dipulihkan_fuzzy"] = int(by_typo.sum())
    else:
        c["nama_typo_dipulihkan_fuzzy"] = 0

    unresolved = ~t["product_resolved"].isin(dim["product_id"])
    c["produk_tak_teridentifikasi_dibuang"] = int(unresolved.sum())
    t = t[~unresolved]

    # 7. Kolom akhir + revenue per baris (bertanda: VOID/REFUND negatif)
    t["line_revenue"] = t["qty"] * t["unit_price"]
    t["payment_method"] = t["payment_method"].map(normalize_payment)
    fact = t[["transaction_id", "line_no", "datetime", "date", "outlet_id",
              "product_resolved", "qty", "unit_price", "line_revenue",
              "payment_method", "status"]].rename(columns={"product_resolved": "product_id"})
    c["baris_keluar"] = len(fact)
    c["trx_ok"] = int((fact["status"] == "OK").sum())
    c["trx_void"] = int((fact["status"] == "VOID").sum())
    c["trx_refund"] = int((fact["status"] == "REFUND").sum())
    return fact.reset_index(drop=True), c


# ---------------------------------------------------------------- orkestrasi


def run_pipeline():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    raw_files = sorted(RAW_DIR.glob("pos_export_*.csv"))
    if not raw_files:
        raise FileNotFoundError("Tidak ada CSV mentah. Jalankan dulu: python -m src.generate_pos_data")

    frames = [pd.read_csv(f, dtype=str, keep_default_na=False) for f in raw_files]
    raw = pd.concat(frames, ignore_index=True)
    master = pd.read_csv(RAW_DIR / "master_produk.csv", dtype=str, keep_default_na=False)

    dim_product, legacy_map, counters = clean_master(master)
    fact, tx_counters = clean_transactions(raw, dim_product, legacy_map)

    dim_outlet = pd.DataFrame(OUTLETS)[["outlet_id", "name", "area"]]

    fact.to_parquet(PROCESSED_DIR / "fact_sales.parquet", index=False)
    dim_product.to_parquet(PROCESSED_DIR / "dim_product.parquet", index=False)
    dim_outlet.to_parquet(PROCESSED_DIR / "dim_outlet.parquet", index=False)

    all_counters = {**counters, **tx_counters, "file_mentah": len(raw_files)}
    (PROCESSED_DIR / "quality_counters.json").write_text(
        json.dumps(all_counters, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return fact, dim_product, dim_outlet, all_counters


if __name__ == "__main__":
    fact, dim_product, _, counters = run_pipeline()
    print(f"[pipeline] baris mentah  : {counters['baris_masuk']:,}")
    print(f"[pipeline] baris bersih  : {counters['baris_keluar']:,}")
    print(f"[pipeline] duplikat hapus: {counters['duplikat_dihapus']:,}")
    print(f"[pipeline] produk dim    : {len(dim_product)}")
    print(f"[pipeline] parquet       : {PROCESSED_DIR}")
