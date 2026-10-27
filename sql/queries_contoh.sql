-- Contoh query SQL yang sering dipakai divisi ( Finance / Operations / Marketing )
-- Jalankan dengan: duckdb data/tanamanies.duckdb  (CLI) atau lewat dashboard/MCP.

-- 1. Finance: omzet harian seluruh outlet, bulan terakhir
SELECT date, SUM(pendapatan) AS omzet_harian
FROM v_daily_revenue
WHERE date >= DATE '2026-09-01'
GROUP BY 1 ORDER BY 1;

-- 2. Operations: perbandingan performa antar outlet
SELECT * FROM v_outlet_summary ORDER BY pendapatan DESC;

-- 3. Marketing: 10 produk terlaris + kontribusi kategorinya
SELECT p.category, p.product_name, SUM(f.qty) AS qty
FROM fact_sales f
JOIN dim_product p USING (product_id)
WHERE f.status = 'OK'
GROUP BY 1, 2
ORDER BY qty DESC
LIMIT 10;

-- 4. Persiapan rapat: pertumbuhan omzet bulanan per outlet
SELECT date_trunc('month', date) AS bulan, outlet_name, SUM(pendapatan) AS omzet
FROM v_daily_revenue
GROUP BY 1, 2
ORDER BY 1, 2;
