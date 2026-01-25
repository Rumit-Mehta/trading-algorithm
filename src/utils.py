import datetime as dt
from typing import List, Tuple
import pandas as pd
import yfinance as yf
import streamlit as st

def _standardise_columns(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """
    Make sure df has single-level columns: Open, High, Low, Close, Adj Close, Volume.
    yfinance sometimes returns MultiIndex columns like ('Close','AAPL').
    """
    if df is None or df.empty:
        return pd.DataFrame()

    # If MultiIndex, try to drop the ticker level
    if isinstance(df.columns, pd.MultiIndex):
        # If the last level contains the provided ticker, xs it
        last_level = df.columns.get_level_values(-1)
        if ticker in last_level:
            df = df.xs(ticker, axis=1, level=-1, drop_level=True)
        else:
            # Flatten generically
            df.columns = ["_".join([str(x) for x in tup if str(x) != ""]) for tup in df.columns]
    return df

@st.cache_data(show_spinner=False)
def fetch_history(ticker: str, start: dt.date, end: dt.date, interval: str = "1d") -> pd.DataFrame:
    """
    Download OHLCV history for a ticker.
    Returns a DataFrame with columns: Date, Open, High, Low, Close, Adj Close, Volume
    """
    try:
        df = yf.download(
            ticker,
            start=start,
            end=end + dt.timedelta(days=1),  # include end date
            interval=interval,
            auto_adjust=False,
            progress=False,
        )
    except Exception:
        return pd.DataFrame()

    if df is None or df.empty:
        return pd.DataFrame()

    # Standardise columns and index
    df = _standardise_columns(df, ticker)
    if df is None or df.empty:
        return pd.DataFrame()

    df.index = pd.to_datetime(df.index)
    df = df.rename_axis("Date").reset_index()
    return df

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    out = df.copy()
    if "Close" in out.columns:
        out["SMA_20"] = out["Close"].rolling(20).mean()
        out["SMA_50"] = out["Close"].rolling(50).mean()
        out["DailyReturn_%"] = out["Close"].pct_change() * 100
        out["RollingHigh_252"] = out["Close"].rolling(252, min_periods=1).max()
        out["RollingLow_252"] = out["Close"].rolling(252, min_periods=1).min()
    return out

def _to_scalar(x) -> float:
    """
    Safely cast a value that might be a numpy scalar / pandas scalar / 1-element Series to float.
    Returns NaN if not possible.
    """
    try:
        # If it's a Series/DataFrame, squeeze
        if isinstance(x, (pd.Series, pd.DataFrame)):
            x = x.squeeze()
            # If it still isn't a scalar, bail
            if isinstance(x, (pd.Series, pd.DataFrame)):
                return float("nan")
        return float(x)
    except Exception:
        return float("nan")

def get_last_scalar(series: pd.Series) -> float:
    if series.empty:
        return float("nan")
    return _to_scalar(series.iloc[-1])

def get_prev_scalar(series: pd.Series) -> float:
    if len(series) < 2:
        return float("nan")
    return _to_scalar(series.iloc[-2])

def quick_stats(df: pd.DataFrame) -> Tuple[float, float, float, float]:
    """
    Return (last_price, change_pct, 52w_high_like, 52w_low_like).
    Uses available window if < 252 trading days.
    """
    if df.empty or "Close" not in df.columns:
        return float("nan"), float("nan"), float("nan"), float("nan")

    last_close = get_last_scalar(df["Close"])
    prev_close = get_prev_scalar(df["Close"])

    if pd.notna(last_close) and pd.notna(prev_close) and prev_close != 0.0:
        change_pct = (last_close / prev_close - 1.0) * 100.0
    else:
        change_pct = float("nan")

    high_52w = get_last_scalar(df["RollingHigh_252"]) if "RollingHigh_252" in df.columns else float("nan")
    low_52w = get_last_scalar(df["RollingLow_252"]) if "RollingLow_252" in df.columns else float("nan")
    return last_close, change_pct, high_52w, low_52w

def parse_tickers(input_str: str) -> List[str]:
    return [t.strip().upper() for t in input_str.replace(";", ",").split(",") if t.strip()]
