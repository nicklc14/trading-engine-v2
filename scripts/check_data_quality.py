import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timezone

DATA_DIR = Path("data")

MARKET_PATH = DATA_DIR / "market_data.csv"
DASHBOARD_WATCHLIST_PATH = DATA_DIR / "dashboard_watchlist.csv"
CANDIDATE_POOL_PATH = DATA_DIR / "candidate_pool.csv"
QUALITY_PATH = DATA_DIR / "data_quality_report.csv"

MAX_DATA_AGE_HOURS = 18
MAX_MARKET_DATE_LAG_DAYS = 4

REQUIRED_MARKET_COLUMNS = [
    "ticker", "price", "volume", "avg_volume_50", "volume_trend",
    "rsi_14", "atr", "atr_pct", "as_of", "market_data_date", "fetched_at_utc",
]

def issue(ticker, issue_type, severity, text, action, freshness=None):
    row = {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "ticker": ticker,
        "issue_type": issue_type,
        "severity": severity,
        "issue": text,
        "suggested_action": action,
        "yfinance_fetched_at_utc": "",
        "latest_market_data_date": "",
        "oldest_market_data_date": "",
        "max_yfinance_age_hours": "",
        "max_market_date_lag_days": "",
    }
    if freshness:
        row.update(freshness)
    return row

def expected_tickers():
    frames = []
    for path in [DASHBOARD_WATCHLIST_PATH, CANDIDATE_POOL_PATH]:
        if path.exists():
            frames.append(pd.read_csv(path))

    if not frames:
        return set()

    df = pd.concat(frames, ignore_index=True)
    if "ticker" not in df.columns:
        return set()

    return set(df["ticker"].astype(str).str.upper().str.strip()) - {""}

def freshness_issue(market, now):
    fetched = pd.to_datetime(market["fetched_at_utc"], errors="coerce", utc=True)
    market_dates = pd.to_datetime(market["market_data_date"], errors="coerce")

    newest_fetch = fetched.max()
    oldest_fetch = fetched.min()
    latest_market_date = market_dates.max()
    oldest_market_date = market_dates.min()

    max_age_hours = "" if pd.isna(oldest_fetch) else round((now - oldest_fetch.to_pydatetime()).total_seconds() / 3600, 1)
    max_lag_days = "" if pd.isna(oldest_market_date) else (now.date() - oldest_market_date.date()).days

    freshness = {
        "yfinance_fetched_at_utc": "" if pd.isna(newest_fetch) else newest_fetch.isoformat(),
        "latest_market_data_date": "" if pd.isna(latest_market_date) else latest_market_date.date().isoformat(),
        "oldest_market_data_date": "" if pd.isna(oldest_market_date) else oldest_market_date.date().isoformat(),
        "max_yfinance_age_hours": max_age_hours,
        "max_market_date_lag_days": max_lag_days,
    }

    if max_age_hours == "" or max_lag_days == "":
        return issue("", "yfinance_freshness", "HIGH", "Yfinance freshness timestamps are missing or invalid", "Rerun GitHub workflow before trading", freshness)

    if max_age_hours > MAX_DATA_AGE_HOURS:
        return issue("", "yfinance_freshness", "HIGH", f"Oldest yfinance fetch is {max_age_hours} hours old", "Rerun GitHub workflow before trading", freshness)

    if max_lag_days > MAX_MARKET_DATE_LAG_DAYS:
        return issue("", "yfinance_freshness", "HIGH", f"Oldest latest-market candle is {max_lag_days} days old", "Check yfinance data or ticker validity", freshness)

    return issue("", "yfinance_freshness", "OK", "Yfinance market data freshness looks OK", "Proceed with normal review", freshness)

def check_data_quality():
    issues = []
    now = datetime.now(timezone.utc)

    if not MARKET_PATH.exists():
        issues.append(issue("", "missing_file", "HIGH", "market_data.csv is missing", "Run update_market_data.py"))
        out = pd.DataFrame(issues)
        out.to_csv(QUALITY_PATH, index=False)
        return out

    market = pd.read_csv(MARKET_PATH)

    for col in REQUIRED_MARKET_COLUMNS:
        if col not in market.columns:
            issues.append(issue("", "missing_column", "HIGH", f"Missing required column: {col}", "Check update_market_data.py output"))

    if "ticker" not in market.columns:
        out = pd.DataFrame(issues)
        out.to_csv(QUALITY_PATH, index=False)
        return out

    market["ticker"] = market["ticker"].astype(str).str.upper().str.strip()

    if "fetched_at_utc" in market.columns and "market_data_date" in market.columns:
        issues.append(freshness_issue(market, now))

    missing_tickers = sorted(expected_tickers() - set(market["ticker"]))
    for ticker in missing_tickers:
        issues.append(issue(ticker, "missing_ticker_data", "HIGH", "Expected ticker is missing from market_data.csv", "Do not trade this ticker until yfinance fetch succeeds"))

    for _, row in market.iterrows():
        ticker = str(row.get("ticker", "")).upper().strip()

        price = pd.to_numeric(row.get("price", np.nan), errors="coerce")
        volume = pd.to_numeric(row.get("volume", np.nan), errors="coerce")
        avg_volume = pd.to_numeric(row.get("avg_volume_50", np.nan), errors="coerce")
        volume_trend = pd.to_numeric(row.get("volume_trend", np.nan), errors="coerce")
        rsi = pd.to_numeric(row.get("rsi_14", np.nan), errors="coerce")
        atr = pd.to_numeric(row.get("atr", np.nan), errors="coerce")
        atr_pct = pd.to_numeric(row.get("atr_pct", np.nan), errors="coerce")

        fetched = pd.to_datetime(row.get("fetched_at_utc", ""), errors="coerce", utc=True)
        if pd.isna(fetched):
            issues.append(issue(ticker, "missing_fetch_time", "HIGH", "Missing fetched_at_utc timestamp", "Rerun GitHub workflow before trading"))

        market_date = pd.to_datetime(row.get("market_data_date", ""), errors="coerce")
        if pd.isna(market_date):
            issues.append(issue(ticker, "missing_market_date", "HIGH", "Missing market_data_date", "Do not trade until latest market date is known"))

        if pd.isna(price) or price <= 0:
            issues.append(issue(ticker, "bad_price", "HIGH", "Missing or invalid price", "Do not trade this ticker"))
        if pd.isna(volume) or volume <= 0:
            issues.append(issue(ticker, "missing_volume", "MEDIUM", "Missing or invalid volume", "Treat volume-based signals as unreliable"))
        if pd.isna(avg_volume) or avg_volume <= 0:
            issues.append(issue(ticker, "missing_avg_volume", "MEDIUM", "Missing 50-day average volume", "Volume trend may be unreliable"))
        if pd.isna(volume_trend):
            issues.append(issue(ticker, "missing_volume_trend", "MEDIUM", "Missing volume trend", "Do not rely on volume confirmation"))
        if pd.isna(rsi):
            issues.append(issue(ticker, "missing_rsi", "LOW", "Missing RSI", "RSI quality score may be unreliable"))
        if pd.isna(atr) or atr <= 0:
            issues.append(issue(ticker, "missing_atr", "HIGH", "Missing or invalid ATR", "Stop loss and sizing may be unreliable"))
        if pd.notna(atr_pct) and atr_pct > 0.20:
            issues.append(issue(ticker, "extreme_volatility", "MEDIUM", "ATR is over 20 percent of price", "Use smaller size unless intentional moonshot"))

    out = pd.DataFrame(issues)
    out.to_csv(QUALITY_PATH, index=False)
    return out

if __name__ == "__main__":
    check_data_quality()
