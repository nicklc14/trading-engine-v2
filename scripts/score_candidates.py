import pandas as pd
import numpy as np
from pathlib import Path
from datetime import date

DATA_DIR = Path("data")

WATCHLIST_PATH = DATA_DIR / "watchlist.csv"
MARKET_PATH = DATA_DIR / "market_data.csv"
TIMING_PATH = DATA_DIR / "market_timing.csv"
DASHBOARD_PATH = DATA_DIR / "dashboard.csv"
CANDIDATE_REVIEW_PATH = DATA_DIR / "candidate_review.csv"

COLUMNS = [
    "ticker","source_list","sector","tier","price","score","trend_score",
    "momentum_score","accelerator_score","timing_action","timing_score",
    "recommendation","why","notes","date_added","candidate_reason"
]

PROMOTE_SCORE = 75
PROMOTE_TIMING_SCORE = 70


def truthy(x):
    return str(x).strip().upper() in ["TRUE", "YES", "1", "Y"]


def score_one(row, market, timing):
    ticker = row["ticker"]
    m = market[market["ticker"] == ticker] if not market.empty else pd.DataFrame()
    t = timing[timing["ticker"] == ticker] if not timing.empty else pd.DataFrame()

    price = np.nan
    score = 22
    trend_score = 0
    momentum_score = 0
    accelerator_score = 50
    timing_action = "WAIT"
    timing_score = 50

    if not m.empty:
        mr = m.iloc[0]
        price = mr.get("price", np.nan)

        rsi = pd.to_numeric(mr.get("rsi_14", np.nan), errors="coerce")
        volume_trend = pd.to_numeric(mr.get("volume_trend", np.nan), errors="coerce")
        gap_pct = pd.to_numeric(mr.get("gap_pct", np.nan), errors="coerce")
        macd_hist = pd.to_numeric(mr.get("macd_histogram", np.nan), errors="coerce")

        trend_score = 25 if pd.notna(macd_hist) and macd_hist > 0 else 0
        momentum_score = 25 if pd.notna(rsi) and 45 <= rsi <= 75 else 0

        if pd.notna(volume_trend) and volume_trend >= 1.5:
            accelerator_score += 20
        if pd.notna(gap_pct) and gap_pct >= 0.03:
            accelerator_score += 20

        accelerator_score = min(accelerator_score, 100)
        score = round(trend_score + momentum_score + accelerator_score)

    if not t.empty:
        tr = t.iloc[0]
        timing_action = tr.get("timing_action", "WAIT")
        timing_score = pd.to_numeric(tr.get("timing_score", 50), errors="coerce")

    return price, score, trend_score, momentum_score, accelerator_score, timing_action, timing_score


def score_candidates(rebalance_only=False):
    watch = pd.read_csv(WATCHLIST_PATH)
    market = pd.read_csv(MARKET_PATH) if MARKET_PATH.exists() else pd.DataFrame()
    timing = pd.read_csv(TIMING_PATH) if TIMING_PATH.exists() else pd.DataFrame()

    watch["ticker"] = watch["ticker"].astype(str).str.upper().str.strip()
    watch["enabled"] = watch["enabled"].apply(truthy)

    if "date_added" not in watch.columns:
        watch["date_added"] = str(date.today())
    if "candidate_reason" not in watch.columns:
        watch["candidate_reason"] = watch.get("notes", "")

    for df in [market, timing]:
        if not df.empty:
            df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()

    scored_rows = []

    for idx, row in watch.iterrows():
        price, score, trend, momentum, accel, timing_action, timing_score = score_one(row, market, timing)

        if score >= PROMOTE_SCORE and timing_score >= PROMOTE_TIMING_SCORE:
            watch.at[idx, "enabled"] = True

        scored_rows.append((row, price, score, trend, momentum, accel, timing_action, timing_score))

    watch.to_csv(WATCHLIST_PATH, index=False)

    if rebalance_only:
        return pd.DataFrame(columns=COLUMNS)

    dashboard_tickers = set()
    if DASHBOARD_PATH.exists():
        dash = pd.read_csv(DASHBOARD_PATH)
        if "ticker" in dash.columns:
            dashboard_tickers = set(dash["ticker"].astype(str).str.upper().str.strip())

    review_rows = []

    for row, price, score, trend, momentum, accel, timing_action, timing_score in scored_rows:
        ticker = row["ticker"]

        if ticker in dashboard_tickers:
            continue

        recommendation = "KEEP CANDIDATE" if score >= 50 else "DISABLED"
        why = "Not currently shown on Dashboard — keep under candidate review" if score >= 50 else "Candidate disabled"

        review_rows.append({
            "ticker": ticker,
            "source_list": "CANDIDATE",
            "sector": row.get("sector", ""),
            "tier": row.get("tier", ""),
            "price": price,
            "score": score,
            "trend_score": trend,
            "momentum_score": momentum,
            "accelerator_score": accel,
            "timing_action": timing_action,
            "timing_score": timing_score,
            "recommendation": recommendation,
            "why": why,
            "notes": row.get("notes", ""),
            "date_added": row.get("date_added", str(date.today())),
            "candidate_reason": row.get("candidate_reason", row.get("notes", "")),
        })

    review = pd.DataFrame(review_rows, columns=COLUMNS)

    if not review.empty:
        review["priority_rank"] = review["recommendation"].map({
            "KEEP CANDIDATE": 1,
            "DISABLED": 4,
        }).fillna(9)

        review = review.sort_values(
            ["priority_rank", "score", "timing_score", "ticker"],
            ascending=[True, False, False, True]
        ).drop(columns=["priority_rank"])

    review.to_csv(CANDIDATE_REVIEW_PATH, index=False)
    return review


if __name__ == "__main__":
    score_candidates()
