import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path("data")
CANDIDATE_PATH = DATA_DIR / "candidate_watchlist.csv"
MARKET_PATH = DATA_DIR / "market_data.csv"
WATCHLIST_PATH = DATA_DIR / "watchlist.csv"
CANDIDATE_REVIEW_PATH = DATA_DIR / "candidate_review.csv"

def truthy(x):
    return str(x).strip().upper() in ["TRUE", "YES", "1", "Y"]

def clamp(x, lo=0, hi=100):
    return max(lo, min(hi, x))

def score_row(row):
    price = row.get("price", np.nan)
    rsi = row.get("rsi_14", np.nan)

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

    rsi_score = 100 if pd.notna(rsi) and 40 <= rsi <= 70 else 50

    final_score = round(
        trend_score * 0.25 +
        momentum_score * 0.30 +
        accelerator_score * 0.25 +
        rsi_score * 0.20
    )

    return clamp(final_score), trend_score, momentum_score, accelerator_score

def timing_action(row):
    score = 50
    gap_pct = row.get("gap_pct", np.nan)
    volume_trend = row.get("volume_trend", np.nan)
    macd_hist = row.get("macd_histogram", np.nan)
    rsi = row.get("rsi_14", np.nan)

    if pd.notna(gap_pct):
        if gap_pct > 0.05:
            score += 25
        elif gap_pct > 0.03:
            score += 15
        elif gap_pct < -0.03:
            score -= 30

    if pd.notna(volume_trend):
        if volume_trend >= 2.0:
            score += 25
        elif volume_trend >= 1.5:
            score += 15
        elif volume_trend < 0.7:
            score -= 15

    if pd.notna(macd_hist):
        score += 10 if macd_hist > 0 else -10

    if pd.notna(rsi):
        if 40 <= rsi <= 70:
            score += 10
        elif rsi > 80 or rsi < 30:
            score -= 15

    score = clamp(round(score))

    if score >= 80:
        return "TIMING CONFIRMED", score
    if score >= 70:
        return "TIMING WATCH", score
    return "WAIT", score

def recommendation(tier, score, trend_score, momentum_score, timing):
    tier = str(tier).upper()

    if score >= 80 and trend_score >= 70 and timing in ["TIMING CONFIRMED", "TIMING WATCH"]:
        return "PROMOTE", "Strong enough for active watchlist"

    if tier in ["MOMENTUM", "MOONSHOT"] and score >= 70 and momentum_score >= 60:
        return "KEEP CANDIDATE", "Interesting but not ready"

    if score < 40:
        return "REMOVE", "Low score and weak setup"

    return "KEEP CANDIDATE", "Monitor for improvement"

def score_candidates():
    if not CANDIDATE_PATH.exists():
        pd.DataFrame(columns=[
            "ticker", "sector", "tier", "enabled", "notes",
            "date_added", "candidate_reason"
        ]).to_csv(CANDIDATE_PATH, index=False)

    candidates = pd.read_csv(CANDIDATE_PATH)

    if candidates.empty:
        out = pd.DataFrame([{
            "status": "No candidates yet"
        }])
        out.to_csv(CANDIDATE_REVIEW_PATH, index=False)
        return out

    for col in ["ticker", "sector", "tier", "enabled", "notes", "date_added", "candidate_reason"]:
        if col not in candidates.columns:
            candidates[col] = ""

    candidates["ticker"] = candidates["ticker"].astype(str).str.upper().str.strip()
    candidates["enabled"] = candidates["enabled"].apply(truthy)
    candidates = candidates[candidates["enabled"]]

    market = pd.read_csv(MARKET_PATH)
    market["ticker"] = market["ticker"].astype(str).str.upper().str.strip()

    active = pd.read_csv(WATCHLIST_PATH) if WATCHLIST_PATH.exists() else pd.DataFrame()
    active_tickers = set(active.get("ticker", pd.Series(dtype=str)).astype(str).str.upper().str.strip())

    df = candidates.merge(market, on="ticker", how="left")

    rows = []

    for _, row in df.iterrows():
        ticker = row["ticker"]
        tier = row.get("tier", "")
        score, trend_score, momentum_score, accelerator_score = score_row(row)
        timing, timing_score = timing_action(row)

        if ticker in active_tickers:
            rec = "ALREADY ACTIVE"
            why = "Ticker already exists in active watchlist"
        else:
            rec, why = recommendation(tier, score, trend_score, momentum_score, timing)

        rows.append({
            "ticker": ticker,
            "sector": row.get("sector", ""),
            "tier": tier,
            "price": row.get("price", np.nan),
            "score": score,
            "trend_score": trend_score,
            "momentum_score": momentum_score,
            "accelerator_score": accelerator_score,
            "timing_action": timing,
            "timing_score": timing_score,
            "recommendation": rec,
            "why": why,
            "notes": row.get("notes", ""),
            "date_added": row.get("date_added", ""),
            "candidate_reason": row.get("candidate_reason", ""),
        })

    out = pd.DataFrame(rows).sort_values(
        ["recommendation", "score", "ticker"],
        ascending=[True, False, True]
    )

    out.to_csv(CANDIDATE_REVIEW_PATH, index=False)
    return out

if __name__ == "__main__":
    score_candidates()
