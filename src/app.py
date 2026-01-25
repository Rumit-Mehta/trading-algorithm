# app.py
import datetime as dt
from typing import List, Tuple

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import yfinance as yf
import numpy as np

st.set_page_config(page_title="Stock Monitor", page_icon="📈", layout="wide")


from utils import (
    fetch_history,
    add_indicators,
    quick_stats,
    parse_tickers,
    get_last_scalar,
    get_prev_scalar
)


def plot_price_volume(df: pd.DataFrame, title: str):
    if df.empty:
        st.info("No data for this period.")
        return

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])

    fig.add_trace(
        go.Candlestick(
            x=df["Date"],
            open=df.get("Open"),
            high=df.get("High"),
            low=df.get("Low"),
            close=df.get("Close"),
            name="Price",
        ),
        row=1, col=1
    )

    if "SMA_20" in df.columns:
        fig.add_trace(go.Scatter(x=df["Date"], y=df["SMA_20"], name="SMA 20", line=dict(width=1.5)), row=1, col=1)
    if "SMA_50" in df.columns:
        fig.add_trace(go.Scatter(x=df["Date"], y=df["SMA_50"], name="SMA 50", line=dict(width=1.5)), row=1, col=1)

    if "Volume" in df.columns:
        fig.add_trace(go.Bar(x=df["Date"], y=df["Volume"], name="Volume", opacity=0.5), row=2, col=1)

    fig.update_layout(
        title=title,
        xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=10, t=50, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    st.plotly_chart(fig, use_container_width=True)

    df["GT/LT"] = df["SMA_20"] > df["SMA_50"]
    df = df.dropna(subset=["SMA_20", "SMA_50"])


    df["Signal"] = ""
    df.loc[(df["GT/LT"] == True) & (df["GT/LT"].shift(-1) == False) & (df["GT/LT"].shift(-1) != None), "Signal"] = "Sell here"
    df.loc[(df["GT/LT"] == False) & (df["GT/LT"].shift(-1) == True) & (df["GT/LT"].shift(-1) != None), "Signal"] = "Buy here"

    st.dataframe(df)


# parse_tickers is now imported from utils


# -----------------------
# Session state (watchlist)
# -----------------------
if "watchlist" not in st.session_state:
    st.session_state.watchlist = []


# -----------------------
# Header
# -----------------------
st.title("📈 Stock Monitor (Streamlit)")
st.caption("Enter one or more tickers, choose a date range, and explore price, volume, moving averages, returns, and quick stats.")


# -----------------------
# Controls (main area only; no sidebar)
# -----------------------
default_start = dt.date.today() - dt.timedelta(days=180)
default_end = dt.date.today()

with st.form("controls", clear_on_submit=False):
    tickers_input = st.text_input("Tickers (comma-separated):", value="AAPL, MSFT, GOOGL")

    c1, c2, c3 = st.columns([1, 1, 1], vertical_alignment="bottom")
    with c1:
        date_range = st.date_input(
            "Date range:",
            value=(default_start, default_end),
            min_value=dt.date(1980, 1, 1),
            max_value=dt.date.today()
        )
    with c2:
        interval = st.selectbox(
            "Interval:",
            options=["1d", "1h", "30m", "15m", "5m", "1wk", "1mo"],
            index=0,
            help="Shorter intervals require shorter date ranges for Yahoo data."
        )
    with c3:
        show_returns = st.checkbox("Show daily returns table", value=False)
        download_as = st.selectbox("Download data as", ["CSV", "Parquet"], index=0)

    submit = st.form_submit_button("Apply filters 🔄")


# Parse/validate dates
if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = default_start, default_end

if start_date > end_date:
    st.error("Start date must be before the end date.")
    st.stop()

# Watchlist controls (inline)
wc1, wc2, wc3 = st.columns([2, 1, 1])
with wc1:
    st.markdown("**Watchlist:** " + (", ".join(st.session_state.watchlist) if st.session_state.watchlist else "_empty_"))
with wc2:
    if st.button("➕ Add to watchlist"):
        st.session_state.watchlist = sorted(set(st.session_state.watchlist) | set(parse_tickers(tickers_input)))
with wc3:
    if st.button("🗑️ Clear watchlist"):
        st.session_state.watchlist = []

st.markdown("---")


# -----------------------
# Summary metrics
# -----------------------
tickers = parse_tickers(tickers_input)
if not tickers:
    st.info("Enter at least one ticker (e.g. `AAPL, MSFT`).")
else:
    summary_cols = st.columns(min(len(tickers), 4) or 1)
    for i, ticker in enumerate(tickers):
        with st.spinner(f"Fetching {ticker}..."):
            df = fetch_history(ticker, start_date, end_date, interval)
            df = add_indicators(df)

        last_price, change_pct, high_52w, low_52w = quick_stats(df)

        with summary_cols[i % len(summary_cols)]:
            st.metric(
                label=f"{ticker} Last Close",
                value="—" if pd.isna(last_price) else f"{last_price:,.2f}",
                delta=None if pd.isna(change_pct) else f"{change_pct:+.2f}%"
            )
            if not pd.isna(high_52w) and not pd.isna(low_52w):
                st.caption(f"52w range: {low_52w:,.2f} → {high_52w:,.2f}")

    # -----------------------
    # Per-ticker detail sections
    # -----------------------
    for ticker in tickers:
        st.markdown("---")
        st.subheader(ticker)

        with st.spinner("Loading chart..."):
            df = fetch_history(ticker, start_date, end_date, interval)
            df = add_indicators(df)

        if df.empty:
            st.warning("No data returned. Check the ticker symbol, interval, or date range.")
            continue

        plot_price_volume(df, f"{ticker} Price & Volume")

        if show_returns and "DailyReturn_%" in df.columns:
            st.write("**Daily Returns (%)**")
            returns_df = df[["Date", "Close", "DailyReturn_%"]].set_index("Date").dropna()
            st.dataframe(
                returns_df.style.format({"Close": "{:,.2f}", "DailyReturn_%": "{:+.2f}"}),
                use_container_width=True
            )

        # Download buttons
        dl_df = df.set_index("Date")
        if download_as == "CSV":
            st.download_button(
                label=f"Download {ticker} data (CSV)",
                data=dl_df.to_csv().encode("utf-8"),
                file_name=f"{ticker}_{start_date}_{end_date}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        else:
            import io
            try:
                import pyarrow as pa
                import pyarrow.parquet as pq
                table = pa.Table.from_pandas(dl_df)
                buf = io.BytesIO()
                pq.write_table(table, buf, compression="snappy")
                st.download_button(
                    label=f"Download {ticker} data (Parquet)",
                    data=buf.getvalue(),
                    file_name=f"{ticker}_{start_date}_{end_date}.parquet",
                    mime="application/octet-stream",
                    use_container_width=True,
                )
            except Exception:
                st.info("Install `pyarrow` to enable Parquet downloads: `pip install pyarrow`")

with st.expander("Tips & Notes"):
    st.markdown(
        """
- Enter multiple tickers separated by commas, e.g. `AAPL, MSFT, NVDA`.
- Short intervals (e.g. `5m`, `15m`) may need a shorter date range due to Yahoo limits.
- **SMA 20/50** show trend; add EMA, RSI, or Bollinger Bands easily.
- The **watchlist** persists for your current session only.
        """
    )