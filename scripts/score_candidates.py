import pandas as pd
import numpy as np
from pathlib import Path
from datetime import date

DATA_DIR = Path("data")

WATCHLIST_PATH = DATA_DIR / "watchlist.csv"
CANDIDATES_PATH = DATA_DIR / "candidates_watchlist.csv"
MARKET_PATH = DATA_DIR / "market_data.csv"
HOLDINGS_PATH = DATA_DIR / "holdings.csv"
CANDIDATE_REVIEW_PATH = DATA_DIR / "candidate_review.csv"

PROMOTE_SCORE = 75
PROMOTE_TIMING_SCORE = 70
DEMOTE_SCORE = 45
KEEP_SCORE = 50

REVIEW_COLUMNS = [
    "ticker", "source_list", "sector", "tier", "price", "score",
    "trend_score", "momentum_score", "accelerator_score",
    "timing_action", "timing_score", "recommendation", "why",
    "notes", "date_added", "candidate_reason"
]


def truthy(x):
    return str(x).strip().upper() in ["TRUE", "YES", "1", "Y"]


def read_csv_safe(path, columns=None):
    if path.exists() and path.stat().st_size > 0:
        return pd.read_csv(path)
    return pd.DataFrame(columns=columns or [])


def normalise(df, default_enabled):
    for col in ["ticker", "sector", "tier", "enabled", "notes", "date_added", "candidate_reason"]:
        if col not in df.columns:
            df[col] = ""

    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
    df = df[df["ticker"] != ""].copy()
    df["enabled"] = df["enabled"].apply(lambda x: truthy(x) if str(x).strip() else default_enabled)
    df["date_added"] = df["date_added"].replace("", str(date.today()))
    df["candidate_reason"] = df["candidate_reason"].where(
        df["candidate_reason"].astype(str).str.strip() != "",
        df["notes"]
    )
    return df


def score_one(row, market):
    ticker = row["ticker"]
    m = market[market["ticker"] == ticker] if not market.empty else pd.DataFrame()

    price = np.nan
    score = 22
    trend_score = 0
    momentum_score = 0
    accelerator_score = 50
    timing_score = 50
    timing_action = "WAIT"

    if not m.empty:
        mr = m.iloc[0]
        price = mr.get("price", np.nan)

        rsi = pd.to_numeric(mr.get("rsi_14", np.nan), errors="coerce")
        volume = pd.to_numeric(mr.get("volume_trend", np.nan), errors="coerce")
        gap = pd.to_numeric(mr.get("gap_pct", np.nan), errors="coerce")
        macd = pd.to_numeric(mr.get("macd_histogram", np.nan), errors="coerce")

        trend_score = 25 if pd.notna(macd) and macd > 0 else 0
        momentum_score = 25 if pd.notna(rsi) and 45 <= rsi <= 75 else 0

        if pd.notna(volume) and volume >= 1.5:
            accelerator_score += 20
        if pd.notna(gap) and gap >= 0.03:
            accelerator_score += 20

        accelerator_score = min(accelerator_score, 100)
        score = round(trend_score + momentum_score + accelerator_score)

        if pd.notna(volume) and volume >= 1.5:
            timing_score += 15
        if pd.notna(gap) and gap >= 0.03:
            timing_score += 15
        if pd.notna(macd) and macd > 0:
            timing_score += 10
        if pd.notna(rsi) and 40 <= rsi <= 70:
            timing_score += 10

        timing_score = max(0, min(100, round(timing_score)))

    if timing_score >= 80:
        timing_action = "TIMING CONFIRMED"
    elif timing_score >= 70:
        timing_action = "TIMING WATCH"

    return price, score, trend_score, momentum_score, accelerator_score, timing_action, timing_score


def score_candidates(rebalance=True, build_review=True):
    watch = normalise(read_csv_safe(WATCHLIST_PATH), True)
    candidates = normalise(read_csv_safe(CANDIDATES_PATH), False)

    market = read_csv_safe(MARKET_PATH)
    if not market.empty and "ticker" in market.columns:
        market["ticker"] = market["ticker"].astype(str).str.upper().str.strip()

    holdings = read_csv_safe(HOLDINGS_PATH)
    held = set()
    if not holdings.empty and "ticker" in holdings.columns:
        held = set(holdings["ticker"].astype(str).str.upper().str.strip())

    if rebalance:
        promoted = []
        kept_candidates = []

        for _, row in candidates.iterrows():
            price, score, trend, momentum, accel, timing_action, timing_score = score_one(row, market)

            manual_promote = truthy(row.get("enabled", False))
            auto_promote = score >= PROMOTE_SCORE and timing_score >= PROMOTE_TIMING_SCORE

            if manual_promote or auto_promote:
                row["enabled"] = True
                promoted.append(row)
            else:
                row["enabled"] = False
                kept_candidates.append(row)

        demoted = []
        kept_watch = []

        for _, row in watch.iterrows():
            price, score, trend, momentum, accel, timing_action, timing_score = score_one(row, market)

            if row["ticker"] not in held and score < DEMOTE_SCORE:
                row["enabled"] = False
                row["candidate_reason"] = "Auto-demoted from active watchlist"
                demoted.append(row)
            else:
                row["enabled"] = True
                kept_watch.append(row)

        watch = pd.DataFrame(kept_watch + promoted)
        candidates = pd.DataFrame(kept_candidates + demoted)

        if not watch.empty:
            watch = watch.drop_duplicates("ticker", keep="first")

        if not candidates.empty:
            if not watch.empty:
                candidates = candidates[~candidates["ticker"].isin(watch["ticker"])]
            candidates = candidates.drop_duplicates("ticker", keep="first")

        watch.to_csv(WATCHLIST_PATH, index=False)
        candidates.to_csv(CANDIDATES_PATH, index=False)

    if not build_review:
        return pd.DataFrame(columns=REVIEW_COLUMNS)

    rows = []

    for _, row in candidates.iterrows():
        price, score, trend, momentum, accel, timing_action, timing_score = score_one(row, market)

        recommendation = "KEEP CANDIDATE" if score >= KEEP_SCORE else "DISABLED"
        why = "Monitor for improvement" if score >= KEEP_SCORE else "Candidate disabled"

        rows.append({
            "ticker": row["ticker"],
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

    review = pd.DataFrame(rows, columns=REVIEW_COLUMNS)

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
