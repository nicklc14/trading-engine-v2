import pandas as pd
import numpy as np
from pathlib import Path
from datetime import date

DATA_DIR = Path("data")

WATCHLIST_PATH = DATA_DIR / "watchlist.csv"
MARKET_PATH = DATA_DIR / "market_data.csv"
TIMING_PATH = DATA_DIR / "market_timing.csv"
CANDIDATE_REVIEW_PATH = DATA_DIR / "candidate_review.csv"

PROMOTE_SCORE = 75
PROMOTE_TIMING_SCORE = 70
KEEP_SCORE = 50


def truthy(x):
    return str(x).strip().upper() in ["TRUE", "YES", "1", "Y", "TRUE"]


def score_candidates():
    watch = pd.read_csv(WATCHLIST_PATH)
    market = pd.read_csv(MARKET_PATH) if MARKET_PATH.exists() else pd.DataFrame()
    timing = pd.read_csv(TIMING_PATH) if TIMING_PATH.exists() else pd.DataFrame()

    watch["ticker"] = watch["ticker"].astype(str).str.upper().str.strip()
    watch["enabled"] = watch["enabled"].apply(truthy)

    if "date_added" not in watch.columns:
        watch["date_added"] = str(date.today())

    if "candidate_reason" not in watch.columns:
        watch["candidate_reason"] = watch.get("notes", "")

    if not market.empty:
        market["ticker"] = market["ticker"].astype(str).str.upper().str.strip()

    if not timing.empty:
        timing["ticker"] = timing["ticker"].astype(str).str.upper().str.strip()

    rows = []

    for _, row in watch.iterrows():
        ticker = row["ticker"]
        m = market[market["ticker"] == ticker]
        t = timing[timing["ticker"] == ticker]

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
            accelerator_score = 50

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

        if score >= PROMOTE_SCORE and timing_score >= PROMOTE_TIMING_SCORE:
            recommendation = "PROMOTE TO WATCHLIST"
            why = "Score and timing meet promotion threshold"
        elif score >= KEEP_SCORE:
            recommendation = "KEEP CANDIDATE"
            why = "Monitor for improvement"
        else:
            recommendation = "DISABLED"
            why = "Candidate disabled"

        rows.append({
            "ticker": ticker,
            "source_list": "CANDIDATE",
            "sector": row.get("sector", ""),
            "tier": row.get("tier", ""),
            "price": price,
            "score": score,
            "trend_score": trend_score,
            "momentum_score": momentum_score,
            "accelerator_score": accelerator_score,
            "timing_action": timing_action,
            "timing_score": timing_score,
            "recommendation": recommendation,
            "why": why,
            "notes": row.get("notes", ""),
            "date_added": row.get("date_added", str(date.today())),
            "candidate_reason": row.get("candidate_reason", row.get("notes", "")),
        })

    review = pd.DataFrame(rows)

    promote_tickers = review.loc[
        review["recommendation"] == "PROMOTE TO WATCHLIST",
        "ticker"
    ]

    watch.loc[watch["ticker"].isin(promote_tickers), "enabled"] = True

    priority = {
        "PROMOTE TO WATCHLIST": 1,
        "KEEP CANDIDATE": 2,
        "WAIT": 3,
        "DISABLED": 4,
    }

    review["priority_rank"] = review["recommendation"].map(priority).fillna(9)

    review = review.sort_values(
        ["priority_rank", "score", "timing_score", "ticker"],
        ascending=[True, False, False, True]
    ).drop(columns=["priority_rank"])

    watch.to_csv(WATCHLIST_PATH, index=False)
    review.to_csv(CANDIDATE_REVIEW_PATH, index=False)

    return review


if __name__ == "__main__":
    score_candidates()
