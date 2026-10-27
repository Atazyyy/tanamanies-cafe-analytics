"""Laporan kualitas data: dokumentasi masalah yang ditemukan & diperbaiki.

Output:
- data/processed/laporan_kualitas_data.md  (untuk audit internal)
- docs/laporan_kualitas_data.md            (versi yang ikut di-commit)
- data/processed/quality_counters.json     (dibaca dashboard)
"""
from __future__ import annotations

import json
from datetime import date

from src.config import DOCS_DIR, PROCESSED_DIR

DESKRIPSI = {
    "file_mentah": "Jumlah file ekspor POS yang digabung",
    "baris_masuk": "Baris mentah dari seluruh file POS",
    "baris_keluar": "Baris bersih siap analisis",
    "tanggal_format_campur_dibersihkan": "Baris dengan 3 format tanggal campur yang disatukan",
    "tanggal_rusak_dibuang": "Tanggal yang tidak bisa diparse (dibuang)",
    "outlet_tidak_dikenal_dibuang": "Nama outlet tak dikenal (dibuang)",
    "harga_rusak_dibuang": "Harga tak bisa dikonversi (dibuang)",
    "qty_negatif_dipulihkan_jadi_void": "Qty negatif tanpa status -> dipulihkan jadi VOID",
    "duplikat_dihapus": "Baris duplikat akibat ekspor ganda",
    "id_legacy_dipetakan": "Baris memakai ID produk lama -> dipetakan ke ID kanonik",
    "id_hilang_dipulihkan_lewat_nama": "product_id kosong -> dipulihkan lewat nama produk",
    "nama_typo_dipulihkan_fuzzy": "Nama produk typo -> dicocokkan fuzzy (difflib)",
    "produk_tak_teridentifikasi_dibuang": "Produk tetap tak teridentifikasi (dibuang)",
    "trx_ok": "Baris transaksi normal (OK)",
    "trx_void": "Baris VOID (dikecualikan dari pendapatan)",
    "trx_refund": "Baris REFUND (dikecualikan dari pendapatan)",
    "master_baris_masuk": "Baris master produk mentah",
    "master_duplikat_id_dihapus": "Duplikat product_id di master",
    "master_legacy_dipetakan": "Baris legacy master yang dipetakan ke produk kanonik",
    "master_tidak_terpetakan": "Baris legacy master yang gagal dipetakan",
}

GRUP = {
    "Volume Data": ["file_mentah", "baris_masuk", "baris_keluar", "trx_ok", "trx_void", "trx_refund"],
    "Masalah Ditemukan & Diperbaiki": [
        "tanggal_format_campur_dibersihkan", "duplikat_dihapus", "id_legacy_dipetakan",
        "id_hilang_dipulihkan_lewat_nama", "nama_typo_dipulihkan_fuzzy",
        "qty_negatif_dipulihkan_jadi_void", "master_duplikat_id_dihapus", "master_legacy_dipetakan",
    ],
    "Data Dibuang (tidak bisa dipulihkan)": [
        "tanggal_rusak_dibuang", "outlet_tidak_dikenal_dibuang", "harga_rusak_dibuang",
        "produk_tak_teridentifikasi_dibuang", "master_tidak_terpetakan",
    ],
}


def render_report(counters: dict) -> str:
    lines = [
        "# Laporan Kualitas Data — Tanamanies Cafe",
        "",
        f"*Periode data: 2026-04-01 s/d 2026-09-30 · Laporan dibuat: {date.today().isoformat()}*",
        "",
        "Dokumen ini menjelaskan setiap masalah data yang ditemukan pipeline pada ekspor",
        "POS mentah, berapa banyak yang berhasil diperbaiki, dan berapa yang dibuang.",
        "Tujuannya: setiap angka di dashboard dapat diaudit sumbernya.",
        "",
    ]
    for grup, keys in GRUP.items():
        lines.append(f"## {grup}")
        lines.append("")
        lines.append("| Indikator | Jumlah baris | Keterangan |")
        lines.append("|---|---:|---|")
        for k in keys:
            if k in counters:
                lines.append(f"| {k} | {counters[k]:,} | {DESKRIPSI.get(k, '-')} |".replace(",", "."))
        lines.append("")
    lines += [
        "## Kebijakan penanganan",
        "",
        "- **Diperbaiki otomatis**: format tanggal, duplikat ekspor, ID legacy, ID hilang,",
        "  typo nama produk (fuzzy matching, cutoff 0.8), qty negatif tanpa status.",
        "- **Dibuang & dicatat**: baris yang tidak bisa dipulihkan dengan percaya diri.",
        "  Tidak ada tebakan diam-diam — semua keputusan tercatat di laporan ini.",
        "- **VOID & REFUND** tetap tersimpan di `fact_sales` (kolom `status`) untuk analisis",
        "  tren pembatalan, tapi dikecualikan dari semua perhitungan pendapatan.",
        "",
    ]
    return "\n".join(lines)


def write_reports(counters: dict) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    md = render_report(counters)
    (PROCESSED_DIR / "laporan_kualitas_data.md").write_text(md, encoding="utf-8")
    (DOCS_DIR / "laporan_kualitas_data.md").write_text(md, encoding="utf-8")


if __name__ == "__main__":
    counters = json.loads((PROCESSED_DIR / "quality_counters.json").read_text(encoding="utf-8"))
    write_reports(counters)
    print(f"[quality] laporan ditulis ke {DOCS_DIR / 'laporan_kualitas_data.md'}")
