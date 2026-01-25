import streamlit as st
import datetime as dt
import pandas as pd
import plotly.graph_objects as go
from utils import fetch_history, parse_tickers

st.set_page_config(page_title="Price Rise Analysis", page_icon="📈", layout="wide")

st.title("📈 Price Rise Analysis")
st.caption("Identify periods where a stock price rises by a specific amount (e.g., 7 pence).")

with st.expander("How to use this page"):
    st.markdown("""
    1. **Enter a Ticker**: Use the sidebar to enter a stock symbol (e.g., `AAPL` or `LLOY.L`).
    2. **Set the Threshold**: Define the minimum price increase you're looking for. 
       * Note: For UK stocks on Yahoo Finance, prices are often in **pence** (e.g., 50.00), so a 7p rise would be `7.00`. For US stocks, prices are in **dollars**, so a 7c rise would be `0.07`.
    3. **Select Periods**: Choose which timeframes to analyze (1-day, 2-day, etc.).
    4. **Analyze**: The chart will highlight every date where the price rose by at least the threshold compared to $N$ days ago.
    """)

# -----------------------
# Sidebar Controls
# -----------------------
with st.sidebar:
    st.header("Settings")
    ticker_input = st.text_input("Ticker:", value="AAPL")
    rise_threshold = st.number_input("Rise Threshold (e.g. 0.07 for 7 pence):", value=0.07, format="%.2f")
    
    st.subheader("Analysis Periods")
    check_1d = st.checkbox("1 Day", value=True)
    check_2d = st.checkbox("2 Days", value=True)
    check_3d = st.checkbox("3 Days", value=True)
    
    periods = []
    if check_1d: periods.append(1)
    if check_2d: periods.append(2)
    if check_3d: periods.append(3)
    
    custom_period = st.number_input("Add Custom Period (days):", value=0, min_value=0)
    if custom_period > 0 and custom_period not in periods:
        periods.append(custom_period)
    
    periods = sorted(periods)

    date_range = st.date_input(
        "Date range:",
        value=(dt.date.today() - dt.timedelta(days=180), dt.date.today()),
        min_value=dt.date(1980, 1, 1),
        max_value=dt.date.today()
    )

# -----------------------
# Data Fetching & Processing
# -----------------------
if not ticker_input:
    st.info("Please enter a ticker symbol in the sidebar.")
    st.stop()

if not periods:
    st.warning("Please select at least one period for analysis.")
    st.stop()

# Parse dates
if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = dt.date.today() - dt.timedelta(days=180), dt.date.today()

with st.spinner(f"Fetching data for {ticker_input}..."):
    # Fetch extra data to account for the lookback period
    max_period = max(periods)
    fetch_start = start_date - dt.timedelta(days=max_period * 2) # Extra buffer for weekends/holidays
    df = fetch_history(ticker_input, fetch_start, end_date, interval="1d")

if df.empty:
    st.error(f"No data found for {ticker_input}. Please check the symbol.")
    st.stop()

# Filter for the requested display range after calculating differences
df_display = df[df['Date'].dt.date >= start_date].copy()

if df_display.empty:
    st.warning("No data available for the selected date range.")
    st.stop()

# -----------------------
# Analysis
# -----------------------
st.subheader(f"Analysis for {ticker_input.upper()}")

results = {}
for p in periods:
    # Calculate difference over P days
    # Note: diff(p) calculates df['Close'] - df['Close'].shift(p)
    col_name = f"Rise_{p}d"
    df[col_name] = df['Close'].diff(p)
    
    # Identify where rise >= threshold
    condition = df[col_name] >= rise_threshold
    df[f"Match_{p}d"] = condition
    
    # Count matches in the display range
    matches = df[(df['Date'].dt.date >= start_date) & (df[f"Match_{p}d"])]
    results[p] = matches

# Display Summary
cols = st.columns(len(periods))
for i, p in enumerate(periods):
    count = len(results[p])
    cols[i].metric(f"{p}-Day Rise (≥{rise_threshold})", f"{count} times")

# -----------------------
# Visualization
# -----------------------
fig = go.Figure()

# Main price line
fig.add_trace(go.Scatter(
    x=df_display['Date'],
    y=df_display['Close'],
    mode='lines',
    name='Close Price',
    line=dict(color='rgba(100, 100, 100, 0.5)', width=2)
))

# Add markers for each period's matches
colors = ['#FF4B4B', '#1C83E1', '#00C781', '#FFAA00', '#7D3CFF']
for i, p in enumerate(periods):
    matches = results[p]
    if not matches.empty:
        fig.add_trace(go.Scatter(
            x=matches['Date'],
            y=matches['Close'],
            mode='markers',
            name=f'{p}-Day Rise Match',
            marker=dict(
                size=10,
                color=colors[i % len(colors)],
                symbol='triangle-up',
                line=dict(width=1, color='white')
            ),
            hovertemplate="<b>Date:</b> %{x}<br>" +
                          "<b>Price:</b> %{y:.2f}<br>" +
                          f"<b>{p}-Day Rise:</b> %{{customdata:.2f}}<extra></extra>",
            customdata=matches[f"Rise_{p}d"]
        ))

fig.update_layout(
    title=f"{ticker_input.upper()} Price with {rise_threshold} Rise Markers",
    xaxis_title="Date",
    yaxis_title="Price",
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    margin=dict(l=0, r=0, t=80, b=0),
    height=600
)

st.plotly_chart(fig, use_container_width=True)

# -----------------------
# Data Table
# -----------------------
with st.expander("View Match Details"):
    all_matches = []
    for p in periods:
        m = results[p].copy()
        m['Period'] = f"{p} Days"
        m['Rise Amount'] = m[f"Rise_{p}d"]
        all_matches.append(m[['Date', 'Close', 'Period', 'Rise Amount']])
    
    if all_matches:
        combined_df = pd.concat(all_matches).sort_values('Date')
        st.dataframe(combined_df.style.format({
            'Close': '{:.2f}',
            'Rise Amount': '{:+.2f}'
        }), use_container_width=True)
    else:
        st.write("No matches found for the selected criteria.")
