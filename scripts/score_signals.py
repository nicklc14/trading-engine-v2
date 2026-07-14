import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path("data")
SIGNALS_PATH = DATA_DIR / "signals.csv"
MARKET_PATH = DATA_DIR / "market_data.csv"
WATCHLIST_PATH = DATA_DIR / "watchlist.csv"

def clamp(x, lo=0, hi=100):
    return max(lo, min(hi, x))

def score_signals():
    watch = pd.read_csv(WATCHLIST_PATH)
    watch["enabled"] = watch["enabled"].astype(str).str.upper().isin(["TRUE", "YES", "1", "Y"])
    watch = watch[watch["enabled"]]

    market = pd.read_csv(MARKET_PATH)
    market["ticker"] = market["ticker"].astype(str).str.upper().str.strip()

    df = watch.merge(market, on="ticker", how="left")

    rows = []

    for _, row in df.iterrows():
        price = row.get("price", np.nan)
        tier = row.get("tier", "QUALITY")

        trend_score = 0
        if pd.notna(price) and pd.notna(row.get("sma_50")) and price > row["sma_50"]:
            trend_score += 40
        if pd.notna(price) and pd.notna(row.get("sma_200")) and price > row["sma_200"]:
            trend_score += 40

        momentum_score = 0
        if pd.notna(row.get("return_1m")) and row["return_1m"] > 0:
            momentum_score += 25
        if pd.notna(row.get("return_3m")) and row["return_3m"] > 0:
            momentum_score += 35
        if pd.notna(row.get("return_6m")) and row["return_6m"] > 0:
            momentum_score += 40

        accelerator_score = 50
        if pd.notna(row.get("macd_histogram")) and row["macd_histogram"] > 0:
            accelerator_score += 25
        if pd.notna(row.get("volume_trend")) and row["volume_trend"] >= 1.5:
            accelerator_score += 25
        accelerator_score = clamp(accelerator_score)

        rsi = row.get("rsi_14", np.nan)
        rsi_score = 100 if pd.notna(rsi) and 40 <= rsi <= 70 else 50

        final_score = round(
            trend_score * 0.25 +
            momentum_score * 0.30 +
            accelerator_score * 0.25 +
            rsi_score * 0.20
        )

        if tier == "MOMENTUM":
            stop_loss = price * 0.80 if pd.notna(price) else np.nan
            trim_price = price * 1.25 if pd.notna(price) else np.nan
        else:
            stop_loss = price * 0.92 if pd.notna(price) else np.nan
            trim_price = price * 1.15 if pd.notna(price) else np.nan

        action = "WATCH"
        if final_score >= 80 and trend_score >= 70:
            action = "BUY"
        elif final_score >= 75:
            action = "BUY SMALL"

        rows.append({
            "ticker": row["ticker"],
            "sector": row.get("sector", ""),
            "tier": tier,
            "price": price,
            "score": final_score,
            "action": action,
            "trend_score": trend_score,
            "momentum_score": momentum_score,
            "accelerator_score": accelerator_score,
            "rsi_14": rsi,
            "gap_pct": row.get("gap_pct", np.nan),
            "volume_trend": row.get("volume_trend", np.nan),
            "macd_histogram": row.get("macd_histogram", np.nan),
            "stop_loss": stop_loss,
            "trim_price": trim_price
        })

    out = pd.DataFrame(rows).sort_values("score", ascending=False)
    out.to_csv(SIGNALS_PATH, index=False)
    return out

if __name__ == "__main__":
    score_signals()
