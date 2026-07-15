import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timezone

DATA_DIR = Path("data")

MARKET_PATH = DATA_DIR / "market_data.csv"
WATCHLIST_PATH = DATA_DIR / "watchlist.csv"
QUALITY_PATH = DATA_DIR / "data_quality_report.csv"

MAX_DATA_AGE_HOURS = 18
MAX_MARKET_DATE_LAG_DAYS = 4

REQUIRED_MARKET_COLUMNS = [
    "ticker",
    "price",
    "volume",
    "avg_volume_50",
    "volume_trend",
    "rsi_14",
    "atr",
    "atr_pct",
    "as_of",
    "market_data_date",
    "fetched_at_utc",
]

def truthy(x):
    return str(x).strip().upper() in ["TRUE", "YES", "1", "Y"]

def issue(ticker, issue_type, severity, text, action):
    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "ticker": ticker,
        "issue_type": issue_type,
        "severity": severity,
        "issue": text,
        "suggested_action": action,
    }

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

    if WATCHLIST_PATH.exists():
        watch = pd.read_csv(WATCHLIST_PATH)
        watch["enabled"] = watch["enabled"].apply(truthy)
        enabled_tickers = set(watch.loc[watch["enabled"], "ticker"].astype(str).str.upper().str.strip())
        fetched_tickers = set(market["ticker"])
        missing_tickers = sorted(enabled_tickers - fetched_tickers)

        for ticker in missing_tickers:
            issues.append(issue(
                ticker,
                "missing_ticker_data",
                "HIGH",
                "Enabled watchlist ticker is missing from market_data.csv",
                "Do not trade this ticker until yfinance fetch succeeds"
            ))

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
        else:
            age_hours = (now - fetched.to_pydatetime()).total_seconds() / 3600
            if age_hours > MAX_DATA_AGE_HOURS:
                issues.append(issue(ticker, "stale_fetch", "HIGH", f"Market data was fetched {age_hours:.1f} hours ago", "Rerun GitHub workflow before trading"))

        market_date = pd.to_datetime(row.get("market_data_date", ""), errors="coerce")
        if pd.isna(market_date):
            issues.append(issue(ticker, "missing_market_date", "HIGH", "Missing market_data_date", "Do not trade until latest market date is known"))
        else:
            lag_days = (now.date() - market_date.date()).days
            if lag_days > MAX_MARKET_DATE_LAG_DAYS:
                issues.append(issue(ticker, "old_market_date", "HIGH", f"Latest market candle is {lag_days} days old", "Check yfinance data or ticker validity"))

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

    if not issues:
        issues.append(issue("", "ok", "OK", "No major data quality issues found", "Proceed with normal review"))

    out = pd.DataFrame(issues)
    out.to_csv(QUALITY_PATH, index=False)
    return out

if __name__ == "__main__":
    check_data_quality()
