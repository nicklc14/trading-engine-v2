import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timezone

DATA_DIR = Path("data")

MARKET_PATH = DATA_DIR / "market_data.csv"
SIGNALS_PATH = DATA_DIR / "signals.csv"
QUALITY_PATH = DATA_DIR / "data_quality_report.csv"

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
]

def check_data_quality():
    if not MARKET_PATH.exists():
        out = pd.DataFrame([{
            "as_of": datetime.now(timezone.utc).isoformat(),
            "ticker": "",
            "issue_type": "missing_file",
            "severity": "HIGH",
            "issue": "market_data.csv is missing",
            "suggested_action": "Run update_market_data.py",
        }])
        out.to_csv(QUALITY_PATH, index=False)
        return out

    market = pd.read_csv(MARKET_PATH)
    issues = []

    for col in REQUIRED_MARKET_COLUMNS:
        if col not in market.columns:
            issues.append({
                "as_of": datetime.now(timezone.utc).isoformat(),
                "ticker": "",
                "issue_type": "missing_column",
                "severity": "HIGH",
                "issue": f"Missing required column: {col}",
                "suggested_action": "Check update_market_data.py output",
            })

    if "ticker" not in market.columns:
        out = pd.DataFrame(issues)
        out.to_csv(QUALITY_PATH, index=False)
        return out

    for _, row in market.iterrows():
        ticker = str(row.get("ticker", "")).upper().strip()

        price = pd.to_numeric(row.get("price", np.nan), errors="coerce")
        volume = pd.to_numeric(row.get("volume", np.nan), errors="coerce")
        avg_volume = pd.to_numeric(row.get("avg_volume_50", np.nan), errors="coerce")
        volume_trend = pd.to_numeric(row.get("volume_trend", np.nan), errors="coerce")
        rsi = pd.to_numeric(row.get("rsi_14", np.nan), errors="coerce")
        atr = pd.to_numeric(row.get("atr", np.nan), errors="coerce")
        atr_pct = pd.to_numeric(row.get("atr_pct", np.nan), errors="coerce")

        if pd.isna(price) or price <= 0:
            issues.append({
                "as_of": datetime.now(timezone.utc).isoformat(),
                "ticker": ticker,
                "issue_type": "bad_price",
                "severity": "HIGH",
                "issue": "Missing or invalid price",
                "suggested_action": "Do not trade until price data is fixed",
            })

        if pd.isna(volume) or volume <= 0:
            issues.append({
                "as_of": datetime.now(timezone.utc).isoformat(),
                "ticker": ticker,
                "issue_type": "missing_volume",
                "severity": "MEDIUM",
                "issue": "Missing or invalid volume",
                "suggested_action": "Treat volume-based signals as unreliable",
            })

        if pd.isna(avg_volume) or avg_volume <= 0:
            issues.append({
                "as_of": datetime.now(timezone.utc).isoformat(),
                "ticker": ticker,
                "issue_type": "missing_avg_volume",
                "severity": "MEDIUM",
                "issue": "Missing 50-day average volume",
                "suggested_action": "Volume trend may be unreliable",
            })

        if pd.isna(volume_trend):
            issues.append({
                "as_of": datetime.now(timezone.utc).isoformat(),
                "ticker": ticker,
                "issue_type": "missing_volume_trend",
                "severity": "MEDIUM",
                "issue": "Missing volume trend",
                "suggested_action": "Do not rely on volume confirmation",
            })

        if pd.isna(rsi):
            issues.append({
                "as_of": datetime.now(timezone.utc).isoformat(),
                "ticker": ticker,
                "issue_type": "missing_rsi",
                "severity": "LOW",
                "issue": "Missing RSI",
                "suggested_action": "RSI quality score may be unreliable",
            })

        if pd.isna(atr) or atr <= 0:
            issues.append({
                "as_of": datetime.now(timezone.utc).isoformat(),
                "ticker": ticker,
                "issue_type": "missing_atr",
                "severity": "HIGH",
                "issue": "Missing or invalid ATR",
                "suggested_action": "Stop loss and sizing may be unreliable",
            })

        if pd.notna(atr_pct) and atr_pct > 0.20:
            issues.append({
                "as_of": datetime.now(timezone.utc).isoformat(),
                "ticker": ticker,
                "issue_type": "extreme_volatility",
                "severity": "MEDIUM",
                "issue": "ATR is over 20 percent of price",
                "suggested_action": "Use smaller size or avoid unless intentional moonshot",
            })

    if not issues:
        issues.append({
            "as_of": datetime.now(timezone.utc).isoformat(),
            "ticker": "",
            "issue_type": "ok",
            "severity": "OK",
            "issue": "No major data quality issues found",
            "suggested_action": "Proceed with normal review",
        })

    out = pd.DataFrame(issues)
    out.to_csv(QUALITY_PATH, index=False)
    return out

if __name__ == "__main__":
    check_data_quality()
