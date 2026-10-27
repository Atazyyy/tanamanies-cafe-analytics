-- ============================================================
-- Tanamanies Cafe Analytics — View analitik (DuckDB)
-- Semua metrik bisnis didefinisikan SATU kali di sini agar
-- dashboard, MCP server, dan divisi lain memakai angka yang sama.
-- ============================================================

-- Pendapatan harian per outlet (JOIN fact ke dim outlet)
CREATE VIEW IF NOT EXISTS v_daily_revenue AS
SELECT
    f.date,
    o.outlet_id,
    o.name AS outlet_name,
    COUNT(DISTINCT f.transaction_id)          AS jumlah_transaksi,
    SUM(f.qty)                                AS item_terjual,
    SUM(f.line_revenue)                       AS pendapatan
FROM fact_sales f
JOIN dim_outlet o USING (outlet_id)
WHERE f.status = 'OK'
GROUP BY 1, 2, 3;

-- Ringkasan per outlet (seluruh periode)
CREATE VIEW IF NOT EXISTS v_outlet_summary AS
SELECT
    o.outlet_id,
    o.name                    AS outlet_name,
    o.area,
    COUNT(DISTINCT f.transaction_id)          AS jumlah_transaksi,
    SUM(f.qty)                                AS item_terjual,
    SUM(f.line_revenue)                       AS pendapatan,
    SUM(f.line_revenue) / COUNT(DISTINCT f.transaction_id) AS rata_belanja
FROM fact_sales f
JOIN dim_outlet o USING (outlet_id)
WHERE f.status = 'OK'
GROUP BY 1, 2, 3;

-- Performa produk (JOIN fact ke dim produk, kategori ikut)
CREATE VIEW IF NOT EXISTS v_product_performance AS
SELECT
    p.product_id,
    p.product_name,
    p.category,
    COUNT(DISTINCT f.transaction_id)          AS jumlah_transaksi,
    SUM(f.qty)                                AS qty_terjual,
    SUM(f.line_revenue)                       AS pendapatan
FROM fact_sales f
JOIN dim_product p USING (product_id)
WHERE f.status = 'OK'
GROUP BY 1, 2, 3;

-- Komposisi metode pembayaran
CREATE VIEW IF NOT EXISTS v_payment_mix AS
SELECT
    f.payment_method,
    COUNT(DISTINCT f.transaction_id)          AS jumlah_transaksi,
    SUM(f.line_revenue)                       AS pendapatan
FROM fact_sales f
WHERE f.status = 'OK'
GROUP BY 1;

-- Pola jam ramai (untuk penjadwalan shift & stok)
CREATE VIEW IF NOT EXISTS v_hourly_pattern AS
SELECT
    o.name                                                    AS outlet_name,
    EXTRACT(dow FROM f.datetime)                              AS dayofweek,  -- 0=Minggu .. 6=Sabtu
    EXTRACT(hour FROM f.datetime)                             AS jam,
    COUNT(DISTINCT f.transaction_id)                          AS jumlah_transaksi
FROM fact_sales f
JOIN dim_outlet o USING (outlet_id)
WHERE f.status = 'OK'
GROUP BY 1, 2, 3;

-- Pendapatan per kategori menu
CREATE VIEW IF NOT EXISTS v_category_revenue AS
SELECT
    p.category,
    SUM(f.qty)                                AS qty_terjual,
    SUM(f.line_revenue)                       AS pendapatan
FROM fact_sales f
JOIN dim_product p USING (product_id)
WHERE f.status = 'OK'
GROUP BY 1;
