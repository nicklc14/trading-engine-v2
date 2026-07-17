import pandas as pd
import numpy as np
import yfinance as yf
from pathlib import Path
from datetime import datetime, timezone

DATA_DIR = Path("data")
DASHBOARD_WATCHLIST_PATH = DATA_DIR / "dashboard_watchlist.csv"
CANDIDATE_POOL_PATH = DATA_DIR / "candidate_pool.csv"
MARKET_PATH = DATA_DIR / "market_data.csv"
REGIME_PATH = DATA_DIR / "market_regime.csv"

def fetch_tickers():
    frames = []

    if DASHBOARD_WATCHLIST_PATH.exists():
        frames.append(pd.read_csv(DASHBOARD_WATCHLIST_PATH))

    if CANDIDATE_POOL_PATH.exists():
        frames.append(pd.read_csv(CANDIDATE_POOL_PATH))

    if not frames:
        return []

    df = pd.concat(frames, ignore_index=True)
    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
    df = df[df["ticker"] != ""]
    return sorted(df["ticker"].drop_duplicates().tolist())

def calc_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def calc_macd(close, fast=12, slow=26, signal=9):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    sig = macd.ewm(span=signal, adjust=False).mean()
    hist = macd - sig
    return macd, sig, hist

def calc_atr(high, low, close, period=14):
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def fetch_one(ticker):
    fetched_at = datetime.now(timezone.utc).isoformat()
    hist = yf.download(ticker, period="1y", interval="1d", auto_adjust=False, progress=False)

    if hist.empty:
        return None

    if isinstance(hist.columns, pd.MultiIndex):
        hist.columns = hist.columns.get_level_values(0)

    close = hist["Close"].dropna()
    if close.empty:
        return None

    price = float(close.iloc[-1])
    macd_line, macd_signal, macd_hist = calc_macd(close)

    volume = hist["Volume"].dropna()
    avg_volume_50 = volume.rolling(50).mean().iloc[-1] if len(volume) >= 50 else np.nan
    current_volume = volume.iloc[-1] if len(volume) else np.nan
    volume_trend = current_volume / avg_volume_50 if pd.notna(avg_volume_50) and avg_volume_50 > 0 else np.nan

    gap_pct = np.nan
    gap_direction = "NONE"

    if len(close) >= 2:
        prev_close = close.iloc[-2]
        open_today = hist["Open"].iloc[-1]
        if prev_close > 0:
            gap_pct = (open_today - prev_close) / prev_close
            if gap_pct > 0.03:
                gap_direction = "UP"
            elif gap_pct < -0.03:
                gap_direction = "DOWN"

    high = hist["High"].dropna()
    low = hist["Low"].dropna()
    atr_series = calc_atr(high, low, close)
    atr = float(atr_series.iloc[-1]) if len(atr_series) and pd.notna(atr_series.iloc[-1]) else np.nan

    market_data_date = hist.index[-1].date().isoformat()

    return {
        "ticker": ticker,
        "price": price,
        "sma_50": float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else np.nan,
        "sma_200": float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else np.nan,
        "rsi_14": float(calc_rsi(close).iloc[-1]) if len(close) >= 20 else np.nan,
        "return_1m": float(price / close.iloc[-21] - 1) if len(close) >= 22 else np.nan,
        "return_3m": float(price / close.iloc[-63] - 1) if len(close) >= 64 else np.nan,
        "return_6m": float(price / close.iloc[-126] - 1) if len(close) >= 127 else np.nan,
        "macd_line": float(macd_line.iloc[-1]),
        "macd_signal": float(macd_signal.iloc[-1]),
        "macd_histogram": float(macd_hist.iloc[-1]),
        "macd_histogram_prev": float(macd_hist.iloc[-2]) if len(macd_hist) >= 2 else np.nan,
        "volume": float(current_volume) if pd.notna(current_volume) else np.nan,
        "avg_volume_50": float(avg_volume_50) if pd.notna(avg_volume_50) else np.nan,
        "volume_trend": float(volume_trend) if pd.notna(volume_trend) else np.nan,
        "gap_pct": float(gap_pct) if pd.notna(gap_pct) else np.nan,
        "gap_direction": gap_direction,
        "atr": atr,
        "atr_pct": atr / price if pd.notna(atr) and price > 0 else np.nan,
        "as_of": datetime.now(timezone.utc).date().isoformat(),
        "market_data_date": market_data_date,
        "fetched_at_utc": fetched_at,
    }

def update_market_data():
    DATA_DIR.mkdir(exist_ok=True)

    tickers = fetch_tickers()

    rows = []
    for ticker in tickers:
        try:
            row = fetch_one(ticker)
            if row:
                rows.append(row)
        except Exception as e:
            print(f"Failed {ticker}: {e}")

    market = pd.DataFrame(rows)
    market.to_csv(MARKET_PATH, index=False)

    spy = fetch_one("SPY")
    regime = "Risk On" if spy and pd.notna(spy.get("sma_200")) and spy["price"] >= spy["sma_200"] else "Risk Off"

    pd.DataFrame([{
        "as_of": datetime.now(timezone.utc).date().isoformat(),
        "market_regime": regime,
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
    }]).to_csv(REGIME_PATH, index=False)

    return market

if __name__ == "__main__":
    update_market_data()
