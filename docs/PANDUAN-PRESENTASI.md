# Panduan Presentasi — Tanamanies Cafe Analytics

Cara mempresentasikan project ini saat interview / demo / video portfolio, khususnya untuk
posisi semacam **AI Systems Engineering / Data Engineer / AI Automation** (contoh konteks:
perusahaan F&B multi-outlet yang butuh pipeline data harian, dashboard, dan AI integration).

---

## 1. Elevator pitch (30 detik, hafalkan)

> "Ini simulasi lengkap masalah yang saya pahami dari bisnis F&B multi-outlet: tiga outlet
> dengan ekspor POS yang formatnya beda-beda dan datanya kotor. Saya bangun pipeline harian
> yang membersihkan ±140 ribu baris itu — dengan setiap perbaikan tercatat dan bisa diaudit —
> memuatnya ke DuckDB, lalu menyajikannya sebagai dashboard performa. Dan karena divisi lain
> tidak bisa SQL, saya tambahkan MCP server supaya AI assistant bisa menjawab pertanyaan
> bisnis langsung dari database yang sudah bersih. Semuanya dibangun dengan AI coding
> assistant, dan setiap hasil AI saya verifikasi — itu cara kerja saya sehari-hari."

## 2. Alur demo 5 menit (urutan jangan diubah)

| Menit | Aksi | Yang kamu katakan |
|---|---|---|
| 0:00–0:30 | Buka **README** di GitHub | Jelaskan diagram alur: POS kotor → pipeline → DuckDB → dashboard + MCP. Tekankan: *18 file CSV, 140 ribu baris, data sengaja dikotori seperti POS asli*. |
| 0:30–1:15 | Buka **`data/sample/pos_export_..._sample.csv`** | "Coba lihat data mentahnya: tanggalnya tiga format, nama outletnya 'dago', 'DAGO', 'Tanamanies dago'. ID produknya ada yang kosong. Ini kondisi nyata POS multi-vendor." |
| 1:15–2:00 | Jalankan `python -m src.run_all --with-data` di terminal | Tunjukkan output 4 langkah. "Setiap angka tercatat — bukan cuma hasil akhir." (Rekam dulu sebelumnya supaya tidak menunggu; atau pakai tanpa `--with-data` yang lebih cepat.) |
| 2:00–2:45 | Buka **`docs/laporan_kualitas_data.md`** | "479 duplikat dihapus, 4.355 baris pakai ID produk lama yang saya petakan, 2.715 ID hilang saya pulihkan lewat nama produk. Yang tidak bisa dipulihkan dibuang dan dicatat — tidak ada tebakan diam-diam." |
| 2:45–4:00 | Buka **dashboard** (tab Ringkasan) | Cerita, jangan baca angka: "Ini omzet harian 3 outlet — terlihat pola akhir pekan dan spike 17 Agustus. KPI-nya punya pembanding periode sebelumnya, jadi bukan angka telanjang." Lalu tunjukkan insight otomatis di bawah grafik. |
| 4:00–4:40 | Tab **Kualitas Data** di dashboard | "Manajemen bisa klik dan lihat sendiri dari mana angkanya. Kepercayaan ke angka itu fitur, bukan dokumen terpisah." |
| 4:40–5:00 | Tab **Produk** atau **Perilaku Pelanggan** (opsional) | Tutup dengan: "Heatmap jam ramai ini yang dipakai Operations untuk jadwal shift. Data yang sama, kebutuhan divisi beda — itu kenapa metriknya didefinisikan sekali di SQL view." |

## 3. Demo MCP (jika waktu ada / sesi teknis)

Buka klien MCP pilihanmu di folder project (`.mcp.json` sesuai README — Claude Desktop, Cursor, maupun ZCode), lalu ketik:

- *"Bandingkan omzet ketiga outlet bulan Agustus 2026."*
- *"5 produk apa yang paling menopang omzet outlet Dago?"*
- *"Jam berapa outlet Buah Batu paling ramai hari Sabtu?"*

Sambil assistant menjawab, sampaikan poin kuncinya:

> "Ini persis jobdesk 'connector data agar setiap divisi mengakses data melalui AI'. Yang penting
> bukan demonya — tapi di sini AI tidak boleh nebak: dia query database yang sudah dibersihkan,
> read-only, dan tool SQL-nya saya guard supaya hanya menerima SELECT."

## 4. Poin bicara yang memetakan project ke jobdesk

| Yang dicari perusahaan | Jawabanmu dari project ini |
|---|---|
| "Menjalankan & memelihara pipeline data harian, memperbaiki saat gagal" | `run_all` satu perintah; test 42 kasus; kalau sumber berubah format, aturan parsing terpusat dan test menangkap regresi |
| "Dashboard dengan angka akurat" | VOID/REFUND dikecualikan dari omzet; metrik didefinisikan sekali di `sql/views.sql` |
| "Data cleansing lintas sumber + dokumentasi" | 3 format tanggal, 16+ metode bayar, duplikat, ID legacy — semua tercatat di laporan kualitas data |
| "Menguasai SQL (JOIN & agregasi)" | `sql/views.sql` + `queries_contoh.sql` — semua view pakai JOIN fact-dim |
| "Git setiap hari: branch, commit, PR, review" | Ceritakan workflow-mu saat membangun ini (lihat §6) |
| "AI coding assistant + verifikasi hasil AI" | Project ini dibangun bersama AI coding assistant (ZCode); kamu yang memutuskan arsitektur, menulis test, dan memverifikasi. Contoh konkret: typo di test terdeteksi pytest, bug `StopIteration` di generator ketemu saat eksekusi — AI menulis, kamu yang QA |
| "MCP / DuckDB (nilai plus)" | Dua-duanya ada dan dipakai nyata di project ini |
| "Keandalan & keamanan data" | MCP read-only + guard SELECT; data mentah tidak di-commit; tidak ada data nyata di repo |
| "Industri F&B / multi-outlet" | Simulasi ini memodelkan persis konteksnya: 3 outlet, POS berbeda, jam ramai, menu & kategori |

## 5. Pertanyaan yang kemungkinan besar ditanya (dan jawabannya)

**"Dari mana datanya?"**
Data sintetis dari generator dengan seed dikunci — bisa direproduksi 100%. Brand fiktif, sengaja,
supaya bebas menunjukkan publik tanpa melanggar kerahasiaan data perusahaan mana pun. Kalau
diterima, pola yang sama saya pakai untuk data asli: sama-sama tidak boleh bocor.

**"Kenapa DuckDB, bukan PostgreSQL?"**
Ini beban analitik lokal (file-based, tanpa server) — cocok untuk pipeline analitik harian skala
ini dan query kolomnya cepat. Kalau data harus diakses bersamaan banyak sistem, saya pindah ke
PostgreSQL; lapisan SQL view-nya tinggal dipindah karena metrik terdefinisi di satu tempat.

**"Bagaimana kamu tahu angkanya benar?"**
Tiga lapis: unit test untuk setiap aturan cleansing, laporan kualitas yang mencatat setiap
perbaikan/dibuangan, dan dashboard menampilkan dengan sadar hanya transaksi berstatus OK.
Rekonsiliasi bisa dilakukan: baris masuk − dibuang − void = baris yang dihitung.

**"Apa yang kamu lakukan kalau pipeline gagal pagi-pagi?"**
Fail-fast di tiap tahap (file tidak ada → error jelas; tanggal rusak → dibuang tapi tercatat,
bukan crash), lalu laporan kualitas menunjukkan di mana masalahnya. Selanjutnya: alert via
Apps Script/Telegram kalau jumlah baris harian menyimpang dari pola.

**"Kenapa Streamlit, bukan web app?"**
Audiensnya internal (manajemen & divisi) — Streamlit paling cepat dari data ke keputusan.
Dashboard ini juga tinggal dibawa ke Next.js kalau diminta, karena semua angka sudah di view SQL.

## 6. Cerita Git (siapkan sebelum interview)

Repo ini dibangun dengan workflow yang bisa diceritakan:

1. `main` selalu stabil — pipeline jalan end-to-end di setiap commit.
2. Fitur dikerjakan di branch (mis. `feature/fuzzy-matching`, `feature/mcp-server`) lalu
   di-merge setelah test hijau.
3. Buka tab **Insights → Network** di GitHub untuk menunjukkan pola commit harian.

> Tips: sebelum interview, buat 1 pull request kecil di repo ini (perbaikan kecil + deskripsi PR
> yang menjelaskan trade-off-nya) supaya ada contoh PR nyata untuk ditunjukkan.

## 7. Kalau diminta kirim video (Loom, 3–4 menit)

1. **0:00** Layar README + elevator pitch di atas.
2. **0:45** Scroll laporan kualitas data sambil menyebut 3 angka besarnya.
3. **1:30** Dashboard: Ringkasan → Kualitas Data → Produk (jangan lebih dari 3 tab).
4. **2:30** Demo MCP: satu pertanyaan bisnis → jawaban dari data.
5. **3:15** Tutup: "Semua ini bisa saya bawa ke data asli kalian minggu pertama."
