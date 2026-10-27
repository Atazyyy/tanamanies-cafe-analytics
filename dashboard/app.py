"""Dashboard performa Tanamanies Cafe (Streamlit).

Menjalankan:  streamlit run dashboard/app.py
Sumber angka: data/tanamanies.duckdb (build dari pipeline; read-only).
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.config import DB_PATH, PROCESSED_DIR  # noqa: E402

st.set_page_config(page_title="Tanamanies Cafe Analytics", page_icon="🌱", layout="wide")

PALETTE = ["#2e7d32", "#66bb6a", "#9ccc65", "#00695c", "#8d6e63", "#ef6c00"]
DOW_LABELS = {0: "Minggu", 1: "Senin", 2: "Selasa", 3: "Rabu", 4: "Kamis", 5: "Jumat", 6: "Sabtu"}
DOW_ORDER = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]


def rp(x) -> str:
    return f"Rp{x:,.0f}".replace(",", ".")


# ---------------------------------------------------------------- data


@st.cache_data(ttl=600)
def load_daily():
    con = duckdb.connect(str(DB_PATH), read_only=True)
    daily = con.execute("SELECT * FROM v_daily_revenue ORDER BY date").df()
    outlets = con.execute("SELECT outlet_id, name FROM dim_outlet ORDER BY name").df()
    min_d, max_d = con.execute("SELECT MIN(date), MAX(date) FROM v_daily_revenue").fetchone()
    con.close()
    daily["date"] = pd.to_datetime(daily["date"])
    return daily, outlets, pd.to_datetime(min_d), pd.to_datetime(max_d)


@st.cache_data(ttl=300)
def scoped(start, end, outlets: tuple):
    """Agregasi yang mengikuti filter tanggal & outlet (query saat dibutuhkan)."""
    ph = ",".join("?" * len(outlets))
    con = duckdb.connect(str(DB_PATH), read_only=True)
    base = f"""
        FROM fact_sales f
        JOIN dim_product p USING (product_id)
        JOIN dim_outlet o USING (outlet_id)
        WHERE f.status = 'OK' AND f.date BETWEEN ? AND ?
          AND o.outlet_id IN ({ph})
    """
    params = [start, end, *outlets]

    products = con.execute(
        f"""SELECT p.category, p.product_name, SUM(f.qty) AS qty_terjual,
                   SUM(f.line_revenue) AS pendapatan
            {base} GROUP BY 1, 2""", params).df()
    payment = con.execute(
        f"""SELECT f.payment_method, COUNT(DISTINCT f.transaction_id) AS transaksi,
                   SUM(f.line_revenue) AS pendapatan
            {base} GROUP BY 1""", params).df()
    hourly = con.execute(
        f"""SELECT EXTRACT(dow FROM f.datetime) AS dow, EXTRACT(hour FROM f.datetime) AS jam,
                   COUNT(DISTINCT f.transaction_id) AS transaksi
            {base} GROUP BY 1, 2""", params).df()
    categories = con.execute(
        f"""SELECT p.category, SUM(f.qty) AS qty_terjual, SUM(f.line_revenue) AS pendapatan
            {base} GROUP BY 1""", params).df()
    con.close()
    return products, payment, hourly, categories


if not DB_PATH.exists():
    st.error("Database belum dibangun. Jalankan dulu: `python -m src.run_all --with-data`")
    st.stop()

daily, outlet_list, min_date, max_date = load_daily()

# ---------------------------------------------------------------- sidebar

st.sidebar.title("🌱 Tanamanies Analytics")
st.sidebar.caption("Kedai kopi & tanaman, Bandung — data simulasi")

pilihan_outlet = st.sidebar.multiselect(
    "Outlet",
    options=outlet_list["outlet_id"].tolist(),
    format_func=lambda oid: outlet_list.set_index("outlet_id").loc[oid, "name"],
    default=outlet_list["outlet_id"].tolist(),
)
if not pilihan_outlet:
    st.sidebar.warning("Pilih minimal satu outlet.")
    st.stop()

rentang = st.sidebar.date_input(
    "Periode", value=(min_date.date(), max_date.date()),
    min_value=min_date.date(), max_value=max_date.date(),
)
if isinstance(rentang, tuple) and len(rentang) == 2:
    start, end = pd.Timestamp(rentang[0]), pd.Timestamp(rentang[1])
else:
    start = end = pd.Timestamp(rentang)

st.sidebar.divider()
st.sidebar.caption(
    "Angka hanya menghitung transaksi berstatus **OK** — VOID & REFUND dikecualikan "
    "agar tidak menggelembungkan omzet."
)

tab_ringkasan, tab_outlet, tab_produk, tab_pelanggan, tab_kualitas = st.tabs(
    ["📊 Ringkasan", "🏬 Outlet", "🥤 Produk", "⏰ Perilaku Pelanggan", "🧹 Kualitas Data"]
)

# data ter-scope (mengikuti filter)
outlet_tuple = tuple(sorted(pilihan_outlet))
products, payment, hourly, categories = scoped(start.date(), end.date(), outlet_tuple)
d = daily[(daily["date"].between(start, end)) & (daily["outlet_id"].isin(pilihan_outlet))]

# ---------------------------------------------------------------- ringkasan

with tab_ringkasan:
    days = (end - start).days + 1
    prev_end, prev_start = start - pd.Timedelta(days=1), start - pd.Timedelta(days=days)
    d_prev = daily[
        (daily["date"].between(prev_start, prev_end)) & (daily["outlet_id"].isin(pilihan_outlet))
    ]

    omzet = d["pendapatan"].sum()
    omzet_prev = d_prev["pendapatan"].sum()
    trx = d["jumlah_transaksi"].sum()
    trx_prev = d_prev["jumlah_transaksi"].sum()
    items = d["item_terjual"].sum()
    n_days = d["date"].nunique()

    delta_rev = (omzet / omzet_prev - 1) * 100 if omzet_prev else None
    delta_trx = (trx / trx_prev - 1) * 100 if trx_prev else None

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Omzet", rp(omzet), f"{delta_rev:+.1f}% vs periode sblm" if delta_rev is not None else None)
    k2.metric("Transaksi", f"{trx:,.0f}".replace(",", "."), f"{delta_trx:+.1f}% vs periode sblm" if delta_trx is not None else None)
    k3.metric("Item Terjual", f"{items:,.0f}".replace(",", "."))
    k4.metric("Rata-rata Belanja", rp(omzet / trx) if trx else "—")
    st.caption(f"Periode {start.date()} – {end.date()} ({n_days} hari beroperasi)")

    if not d.empty:
        fig = px.area(
            d, x="date", y="pendapatan", color="outlet_name",
            labels={"date": "", "pendapatan": "Omzet (Rp)", "outlet_name": "Outlet"},
            color_discrete_sequence=PALETTE,
        )
        fig.update_layout(height=340, legend_title_text="", hovermode="x unified",
                          yaxis_tickprefix="Rp", template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)

    # Insight otomatis
    if not products.empty and not hourly.empty:
        best_outlet = d.groupby("outlet_name")["pendapatan"].sum().idxmax()
        top_prod = products.sort_values("qty_terjual", ascending=False).iloc[0]
        jam_terramai = int(hourly.groupby("jam")["transaksi"].sum().idxmax())
        weekend_share = (d[d["date"].dt.weekday >= 5]["pendapatan"].sum() / omzet * 100) if omzet else 0
        pay_top = payment.sort_values("pendapatan", ascending=False).iloc[0]
        st.info(
            f"**Insight cepat:** outlet terbaik **{best_outlet}** · produk terlaris "
            f"**{top_prod['product_name']}** ({int(top_prod['qty_terjual']):,} cup/pcs)".replace(",", ".")
            + f" · jam tersibuk **{jam_terramai}.00** · akhir pekan menyumbang **{weekend_share:.0f}%** omzet"
            + f" · pembayaran dominan via **{pay_top['payment_method']}**."
        )

# ---------------------------------------------------------------- outlet

with tab_outlet:
    c1, c2 = st.columns([2, 3])
    with c1:
        per_outlet = d.groupby("outlet_name")["pendapatan"].sum().reset_index()
        fig = px.bar(per_outlet, x="outlet_name", y="pendapatan", color="outlet_name",
                     labels={"outlet_name": "", "pendapatan": "Omzet (Rp)"},
                     color_discrete_sequence=PALETTE)
        fig.update_layout(height=320, showlegend=False, template="plotly_white", yaxis_tickprefix="Rp")
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        bulanan = (
            d.assign(bulan=d["date"].dt.strftime("%b %Y"))
            .groupby(["bulan", "outlet_name"])["pendapatan"].sum().reset_index()
        )
        fig = px.line(bulanan, x="bulan", y="pendapatan", color="outlet_name", markers=True,
                      labels={"pendapatan": "Omzet (Rp)", "bulan": ""},
                      color_discrete_sequence=PALETTE)
        fig.update_layout(height=320, legend_title_text="", template="plotly_white", yaxis_tickprefix="Rp")
        st.plotly_chart(fig, use_container_width=True)
    st.dataframe(
        d.groupby("outlet_name")
        .agg(Omzet=("pendapatan", "sum"), Transaksi=("jumlah_transaksi", "sum"),
             Item=("item_terjual", "sum"))
        .assign(**{"Rata-rata Belanja": lambda x: x["Omzet"] / x["Transaksi"]})
        .style.format({"Omzet": rp, "Rata-rata Belanja": rp, "Transaksi": "{:,.0f}", "Item": "{:,.0f}"}),
        use_container_width=True,
    )

# ---------------------------------------------------------------- produk

with tab_produk:
    pilihan_kategori = st.multiselect(
        "Kategori", options=sorted(categories["category"].unique()),
        default=sorted(categories["category"].unique()),
    )
    p = products[products["category"].isin(pilihan_kategori)]
    c1, c2 = st.columns(2)
    with c1:
        top10 = p.sort_values("pendapatan", ascending=False).head(10).iloc[::-1]
        fig = px.bar(top10, x="pendapatan", y="product_name", orientation="h",
                     color="category", labels={"pendapatan": "Omzet (Rp)", "product_name": ""},
                     color_discrete_sequence=PALETTE)
        fig.update_layout(height=380, showlegend=False, template="plotly_white", xaxis_tickprefix="Rp")
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig = px.bar(categories.sort_values("pendapatan"), x="pendapatan", y="category",
                     orientation="h", color="category",
                     labels={"pendapatan": "Omzet (Rp)", "category": ""},
                     color_discrete_sequence=PALETTE)
        fig.update_layout(height=380, showlegend=False, template="plotly_white", xaxis_tickprefix="Rp")
        st.plotly_chart(fig, use_container_width=True)
    st.dataframe(
        p.sort_values("pendapatan", ascending=False).rename(
            columns={"product_name": "Produk", "category": "Kategori",
                     "qty_terjual": "Qty", "pendapatan": "Omzet"}
        ).style.format({"Omzet": rp, "Qty": "{:,.0f}"}),
        use_container_width=True, height=320,
    )

# ---------------------------------------------------------------- pelanggan

with tab_pelanggan:
    c1, c2 = st.columns([3, 2])
    heat = (
        hourly.assign(hari=hourly["dow"].map(DOW_LABELS))
        .pivot_table(index="hari", columns="jam", values="transaksi", aggfunc="sum")
        .reindex(DOW_ORDER)
        .fillna(0)
    )
    with c1:
        fig = px.imshow(heat, aspect="auto", color_continuous_scale="Greens",
                        labels={"x": "Jam", "y": "", "color": "Transaksi"})
        fig.update_layout(height=340, template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Kepadatan transaksi per jam — dasar penjadwalan shift barista & ketersediaan stok.")
    with c2:
        fig = px.pie(payment, names="payment_method", values="pendapatan", hole=0.55,
                     color_discrete_sequence=PALETTE)
        fig.update_layout(height=340, template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Komposisi metode pembayaran (berdasarkan omzet).")

# ---------------------------------------------------------------- kualitas data

with tab_kualitas:
    counter_file = PROCESSED_DIR / "quality_counters.json"
    if counter_file.exists():
        import json

        from src.quality_report import DESKRIPSI, GRUP

        counters = json.loads(counter_file.read_text(encoding="utf-8"))
        m1, m2, m3 = st.columns(3)
        m1.metric("Baris mentah", f"{counters.get('baris_masuk', 0):,}".replace(",", "."))
        m2.metric("Baris bersih", f"{counters.get('baris_keluar', 0):,}".replace(",", "."))
        m3.metric("Perbaikan tercatat",
                  f"{sum(counters.get(k, 0) for k in GRUP['Masalah Ditemukan & Diperbaiki']):,}".replace(",", "."))
        st.caption("Setiap perbaikan dicatat — angka dashboard bisa diaudit sampai ke file mentah.")
        for grup, keys in GRUP.items():
            with st.expander(f"**{grup}**"):
                rows = [
                    {"Indikator": k, "Jumlah": counters.get(k, 0), "Keterangan": DESKRIPSI.get(k, "")}
                    for k in keys if k in counters
                ]
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("Jalankan pipeline dulu untuk menghasilkan laporan kualitas data.")

st.divider()
st.caption(
    "🌱 Tanamanies Cafe — brand & data fiktif untuk portofolio. "
    "Dibangun dengan Python, DuckDB & Streamlit, dikembangkan bersama AI coding assistant (Claude Code) "
    "oleh [Agni Miftah Fauzi](https://github.com/Atazyyy) · [atapdigital.id](https://atapdigital.id)"
)
