# Laporan Kualitas Data — Tanamanies Cafe

*Periode data: 2026-04-01 s/d 2026-09-30 · Laporan dibuat: 2026-10-28*

Dokumen ini menjelaskan setiap masalah data yang ditemukan pipeline pada ekspor
POS mentah, berapa banyak yang berhasil diperbaiki, dan berapa yang dibuang.
Tujuannya: setiap angka di dashboard dapat diaudit sumbernya.

## Volume Data

| Indikator | Jumlah baris | Keterangan |
|---|---:|---|
| file_mentah | 18 | Jumlah file ekspor POS yang digabung |
| baris_masuk | 139.832 | Baris mentah dari seluruh file POS |
| baris_keluar | 139.353 | Baris bersih siap analisis |
| trx_ok | 138.185 | Baris transaksi normal (OK) |
| trx_void | 822 | Baris VOID (dikecualikan dari pendapatan) |
| trx_refund | 346 | Baris REFUND (dikecualikan dari pendapatan) |

## Masalah Ditemukan & Diperbaiki

| Indikator | Jumlah baris | Keterangan |
|---|---:|---|
| tanggal_format_campur_dibersihkan | 139.832 | Baris dengan 3 format tanggal campur yang disatukan |
| duplikat_dihapus | 479 | Baris duplikat akibat ekspor ganda |
| id_legacy_dipetakan | 4.355 | Baris memakai ID produk lama -> dipetakan ke ID kanonik |
| id_hilang_dipulihkan_lewat_nama | 2.715 | product_id kosong -> dipulihkan lewat nama produk |
| nama_typo_dipulihkan_fuzzy | 3 | Nama produk typo -> dicocokkan fuzzy (difflib) |
| qty_negatif_dipulihkan_jadi_void | 0 | Qty negatif tanpa status -> dipulihkan jadi VOID |
| master_duplikat_id_dihapus | 0 | Duplikat product_id di master |
| master_legacy_dipetakan | 6 | Baris legacy master yang dipetakan ke produk kanonik |

## Data Dibuang (tidak bisa dipulihkan)

| Indikator | Jumlah baris | Keterangan |
|---|---:|---|
| tanggal_rusak_dibuang | 0 | Tanggal yang tidak bisa diparse (dibuang) |
| outlet_tidak_dikenal_dibuang | 0 | Nama outlet tak dikenal (dibuang) |
| harga_rusak_dibuang | 0 | Harga tak bisa dikonversi (dibuang) |
| produk_tak_teridentifikasi_dibuang | 0 | Produk tetap tak teridentifikasi (dibuang) |
| master_tidak_terpetakan | 0 | Baris legacy master yang gagal dipetakan |

## Kebijakan penanganan

- **Diperbaiki otomatis**: format tanggal, duplikat ekspor, ID legacy, ID hilang,
  typo nama produk (fuzzy matching, cutoff 0.8), qty negatif tanpa status.
- **Dibuang & dicatat**: baris yang tidak bisa dipulihkan dengan percaya diri.
  Tidak ada tebakan diam-diam — semua keputusan tercatat di laporan ini.
- **VOID & REFUND** tetap tersimpan di `fact_sales` (kolom `status`) untuk analisis
  tren pembatalan, tapi dikecualikan dari semua perhitungan pendapatan.
