"""Generator data POS simulasi untuk Tanamanies Cafe.

Menghasilkan ekspor CSV per outlet per bulan (kondisi POS multi-vendor) plus
file master produk, dengan data yang sengaja "dikotori" agar menyerupai
kondisi nyata:

- Format tanggal campur (3 varian) antar file ekspor
- Nama outlet tidak konsisten (huruf besar/kecil, spasi, sebutan pendek)
- Master produk berisi duplikat: ID lama (legacy), nama berbeda kapital,
  dan typo yang harus dicocokkan secara fuzzy
- Harga sebagian tersimpan sebagai teks berformat Indonesia ("18.000")
- Baris transaksi terduplikasi
- Transaksi VOID (per baris) dan REFUND (per transaksi)

Seed RNG dikunci agar angka dapat direproduksi (penting untuk demo).
"""
from __future__ import annotations

import csv
import random
import re
from datetime import date, datetime, timedelta

from src.config import DATA_END, DATA_START, OUTLETS, RAW_DIR


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).strip().lower())

# (product_id, nama, kategori, harga)
MENU = [
    ("P001", "Kopi Susu Aren", "Kopi Susu", 18000),
    ("P002", "Kopi Susu Gula Pasir", "Kopi Susu", 17000),
    ("P003", "Kopi Susu Pandan", "Kopi Susu", 20000),
    ("P004", "Kopi Susu Kelapa", "Kopi Susu", 20000),
    ("P005", "Es Kopi Tanamanies", "Kopi Susu", 22000),
    ("P006", "Kopi Susu Cokelat", "Kopi Susu", 19000),
    ("P007", "Americano", "Kopi Hitam", 16000),
    ("P008", "V60 Gayo", "Kopi Hitam", 25000),
    ("P009", "Japanese Iced Coffee", "Kopi Hitam", 24000),
    ("P010", "Long Black", "Kopi Hitam", 17000),
    ("P011", "Matcha Latte", "Non-Kopi", 24000),
    ("P012", "Chocolate Signature", "Non-Kopi", 22000),
    ("P013", "Red Velvet Latte", "Non-Kopi", 21000),
    ("P014", "Teh Tarik", "Non-Kopi", 18000),
    ("P015", "Lemon Tea", "Non-Kopi", 14000),
    ("P016", "Lychee Sparkling", "Non-Kopi", 20000),
    ("P017", "Butterscotch Latte", "Signature", 26000),
    ("P018", "Es Kopi Daun Mint", "Signature", 24000),
    ("P019", "Pandan Coffee", "Signature", 25000),
    ("P020", "Kopi Kelapa Muda", "Signature", 28000),
    ("P021", "Butter Croissant", "Pastry", 22000),
    ("P022", "Choco Croissant", "Pastry", 23000),
    ("P023", "Cinnamon Roll", "Pastry", 24000),
    ("P024", "Banana Cake", "Pastry", 18000),
    ("P025", "French Fries", "Snack", 18000),
    ("P026", "Chicken Katsu", "Snack", 25000),
    ("P027", "Pisang Goreng Keju", "Snack", 20000),
    ("P028", "Roti Bakar Tanamanies", "Snack", 17000),
]

# Master "kotor": baris duplikat dari POS lama outlet Buah Batu
LEGACY_PRODUCTS = [
    ("L001", "ES KOPI TANAMANIES", "Kopi Susu", "22000"),
    ("L002", "kopi susu aren", "kopi susu", 18000),
    ("L003", "Matcha Latte ", "NonKopi", "24.000"),
    ("L004", "Butter Croisant", "Pastry", 22000),
    ("L005", "Teh Tarik", "non kopi", 18000),
    ("L006", "Cinamon Roll", "Pastry ", "24.000"),
]

# Produk lama dipakai oleh POS lama di outlet tertentu
LEGACY_BY_CANONICAL = {_norm(name): (pid, name) for pid, name, _, _ in LEGACY_PRODUCTS}

PAYMENTS = [("QRIS", 45), ("Cash", 25), ("Debit", 20), ("E-Wallet", 10)]
PAYMENT_VARIANTS = {
    "QRIS": ["QRIS", "qris", "QR", "Qris "],
    "Cash": ["Cash", "CASH", "cash", "Tunai"],
    "Debit": ["Debit", "debit", "DEBIT", "Kartu Debit"],
    "E-Wallet": ["OVO", "GoPay", "gopay", "ShopeePay"],
}

OUTLET_VARIANTS = {
    "OUT01": ["Tanamanies Dago", "dago", "DAGO", "Tanamanies dago ", "tanamanies dago"],
    "OUT02": ["Tanamanies Buah Batu", "buah batu", "BUAH BATU", "Tanamanies buah batu "],
    "OUT03": ["Tanamanies Dipatiukur", "dipatiukur", "DIPATIUKUR", "tanamanies dipatiukur"],
}

OUTLET_TX_SUFFIX = {"OUT01": "DGO", "OUT02": "BBT", "OUT03": "DPK"}

TYPO_MAP = {
    "Kopi Susu Aren": "Kopi Susu Arren",
    "Matcha Latte": "Matcha Lette",
    "Butter Croissant": "Butter Croisant",
    "Cinnamon Roll": "Cinamon Roll",
}

CATEGORY_VARIANTS = {
    "Kopi Susu": ["Kopi Susu", "kopi susu", "KOPI SUSU"],
    "Kopi Hitam": ["Kopi Hitam", "kopi hitam", "Kopi hitam "],
    "Non-Kopi": ["Non-Kopi", "non kopi", "NONKOPI"],
    "Signature": ["Signature", "signature", "SIGNATURE "],
    "Pastry": ["Pastry", "pastry", "PASTRY"],
    "Snack": ["Snack", "snack ", "SNACK"],
}

WEEKDAY_FACTOR = {0: 1.0, 1: 0.95, 2: 0.95, 3: 1.0, 4: 1.15, 5: 1.4, 6: 1.3}
HOURS = list(range(7, 23))
HOUR_WEIGHTS = [2, 6, 8, 7, 6, 9, 10, 8, 5, 4, 4, 5, 6, 7, 6, 3]

# Produk favorit diberi bobot lebih besar
POPULAR = {"P001", "P005", "P007", "P011", "P021", "P017"}


def _fmt_date(dt: datetime, rng: random.Random) -> str:
    r = rng.random()
    if r < 0.85:
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    if r < 0.95:
        return dt.strftime("%d/%m/%Y %H:%M")
    return dt.strftime("%Y/%m/%d %H:%M")


def _dirty_name(name: str, rng: random.Random) -> str:
    r = rng.random()
    if r < 0.012:
        return name.upper()
    if r < 0.024:
        return name.lower() + "  "
    if r < 0.032:
        return TYPO_MAP.get(name, name)
    return name


def _dirty_outlet(outlet_id: str, rng: random.Random) -> str:
    variants = OUTLET_VARIANTS[outlet_id]
    if rng.random() < 0.15:
        return rng.choice(variants[1:])
    return variants[0]


def _dirty_price(price: int, rng: random.Random) -> int | str:
    if rng.random() < 0.05:
        return f"{price:,}".replace(",", ".")
    return price


def _dirty_payment(method: str, rng: random.Random) -> str:
    variants = PAYMENT_VARIANTS[method]
    if rng.random() < 0.18:
        return rng.choice(variants)
    return method


def generate_master(path) -> None:
    """Tulis master produk 'kotor' (kanonik + duplikat legacy)."""
    rng = random.Random(7)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["product_id", "product_name", "category", "unit_price"])
        for pid, name, cat, price in MENU:
            cat_out = rng.choice(CATEGORY_VARIANTS[cat]) if rng.random() < 0.2 else cat
            w.writerow([pid, name, cat_out, _dirty_price(price, rng)])
        for pid, name, cat, price in LEGACY_PRODUCTS:
            w.writerow([pid, name, cat, price])


def generate() -> int:
    """Generate seluruh ekspor POS. Mengembalikan jumlah baris tertulis."""
    rng = random.Random(42)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    generate_master(RAW_DIR / "master_produk.csv")

    menu_ids = [m[0] for m in MENU]
    menu_meta = {m[0]: m for m in MENU}
    weights = [3 if m[0] in POPULAR else 2 if m[1] in ("Kopi Susu", "Signature") else 1 for m in MENU]

    start = date.fromisoformat(DATA_START)
    end = date.fromisoformat(DATA_END)
    buffer: dict[str, list] = {}

    d = start
    while d <= end:
        growth = 1.0 + (d.month - start.month) * 0.02  # tren tumbuh ~2%/bulan
        spike = 1.6 if d == date(2026, 8, 17) else 1.0  # kampanye tanggal merah
        for outlet in OUTLETS:
            n_tx = int(
                outlet["daily_tx_base"] * WEEKDAY_FACTOR[d.weekday()] * growth * spike
                * rng.uniform(0.9, 1.1)
            )
            oid = outlet["outlet_id"]
            use_legacy_pos = oid == "OUT02"  # outlet ini masih POS lama
            for seq in range(1, n_tx + 1):
                trx_id = f"TRX{d.strftime('%y%m%d')}{OUTLET_TX_SUFFIX[oid]}{seq:05d}"
                refund = rng.random() < 0.0025
                for line_no in range(1, rng.choices([1, 2, 3, 4], weights=[45, 30, 17, 8])[0] + 1):
                    pid = rng.choices(menu_ids, weights=weights)[0]
                    _, name, _, price = menu_meta[pid]
                    if use_legacy_pos and rng.random() < 0.4:
                        pid_out, name_out = LEGACY_BY_CANONICAL.get(_norm(name), (pid, name))
                    else:
                        pid_out, name_out = pid, name
                    if rng.random() < 0.02:
                        pid_out = ""  # ID hilang, harus dipulihkan lewat nama
                    qty = rng.choices([1, 2], weights=[88, 12])[0]
                    status = "OK"
                    if refund:
                        qty, status = -qty, "REFUND"
                    elif rng.random() < 0.006:
                        qty, status = -qty, "VOID"
                    hour = rng.choices(HOURS, weights=HOUR_WEIGHTS)[0]
                    ts = datetime(d.year, d.month, d.day, hour, rng.randint(0, 59), rng.randint(0, 59))
                    pay = rng.choices([p for p, _ in PAYMENTS], weights=[w for _, w in PAYMENTS])[0]
                    row = [
                        trx_id,
                        line_no,
                        _fmt_date(ts, rng),
                        _dirty_outlet(oid, rng),
                        pid_out,
                        _dirty_name(name_out, rng),
                        qty,
                        _dirty_price(price, rng),
                        _dirty_payment(pay, rng),
                        status if status != "OK" else ("" if rng.random() < 0.7 else "OK"),
                    ]
                    buffer.setdefault(f"{oid}-{d.strftime('%Y-%m')}", []).append(row)
        d += timedelta(days=1)

    total = 0
    for key, rows in buffer.items():
        oid, ym = key.split("-", 1)
        oid_slug = {"OUT01": "dago", "OUT02": "buahbatu", "OUT03": "dipatiukur"}[oid]
        path = RAW_DIR / f"pos_export_{oid_slug}_{ym}.csv"
        # Duplikasi acak 0,35% baris (ekspor ganda)
        extra = rng.sample(rows, k=int(len(rows) * 0.0035))
        rows_out = rows + extra
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["transaction_id", "line_no", "datetime", "outlet", "product_id",
                        "product_name", "qty", "unit_price", "payment_method", "status"])
            w.writerows(rows_out)
        total += len(rows_out)
    return total


if __name__ == "__main__":
    n = generate()
    print(f"[generate] {n:,} baris mentah ditulis ke {RAW_DIR}")
