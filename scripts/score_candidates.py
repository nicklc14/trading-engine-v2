import pandas as pd
import numpy as np
from pathlib import Path
from datetime import date

DATA_DIR = Path("data")

WATCHLIST_PATH = DATA_DIR / "watchlist.csv"
CANDIDATES_PATH = DATA_DIR / "candidate_watchlist.csv"
MARKET_PATH = DATA_DIR / "market_data.csv"
HOLDINGS_PATH = DATA_DIR / "holdings.csv"
CANDIDATE_REVIEW_PATH = DATA_DIR / "candidate_review.csv"

ACTIVE_NON_HELD_LIMIT = 5
MOMENTUM_SOFT_INCLUDE_SCORE_GAP = 10
KEEP_SCORE = 50

BASE_COLUMNS = [
    "ticker", "sector", "tier", "enabled", "notes",
    "date_added", "candidate_reason",
    "last_reviewed", "review_count", "status_reason",
]

REVIEW_COLUMNS = [
    "ticker", "source_list", "sector", "tier", "price", "score",
    "trend_score", "momentum_score", "accelerator_score",
    "timing_action", "timing_score", "recommendation", "why",
    "notes", "date_added", "candidate_reason",
    "last_reviewed", "review_count", "status_reason",
]

def truthy(x):
    return str(x).strip().upper() in ["TRUE", "YES", "1", "Y"]

def read_csv_safe(path, columns=None):
    if path.exists() and path.stat().st_size > 0:
        return pd.read_csv(path)
    return pd.DataFrame(columns=columns or [])

def normalise(df, default_enabled):
    for col in BASE_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
    df = df[df["ticker"] != ""].copy()
    df["enabled"] = df["enabled"].apply(lambda x: truthy(x) if str(x).strip() else default_enabled)

    today = str(date.today())
    df["date_added"] = df["date_added"].replace("", today)
    df["last_reviewed"] = df["last_reviewed"].replace("", "")
    df["review_count"] = pd.to_numeric(df["review_count"], errors="coerce").fillna(0).astype(int)
    df["candidate_reason"] = df["candidate_reason"].where(
        df["candidate_reason"].astype(str).str.strip() != "",
        df["notes"]
    )

    return df[BASE_COLUMNS]

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

def touch_review(row, reason):
    row = row.copy()
    today = str(date.today())
    row["last_reviewed"] = today
    row["review_count"] = int(pd.to_numeric(row.get("review_count", 0), errors="coerce") or 0) + 1
    row["status_reason"] = reason
    return row

def tier_rank(tier):
    tier = str(tier).upper()
    if tier == "MOONSHOT":
        return 3
    if tier == "MOMENTUM":
        return 2
    if tier == "QUALITY":
        return 1
    return 0

def select_active_non_held(non_held):
    ranked = non_held.sort_values(
        ["_score", "_timing_score", "_tier_rank", "ticker"],
        ascending=[False, False, False, True]
    )

    selected = ranked.head(ACTIVE_NON_HELD_LIMIT).copy()

    if selected.empty:
        return selected, ranked.iloc[0:0].copy()

    has_momentum = (selected["tier"].astype(str).str.upper() == "MOMENTUM").any()

    if not has_momentum:
        momentum_pool = ranked[ranked["tier"].astype(str).str.upper() == "MOMENTUM"]

        if not momentum_pool.empty:
            best_momentum = momentum_pool.iloc[0]
            weakest_selected = selected.sort_values(
                ["_score", "_timing_score", "_tier_rank", "ticker"],
                ascending=[True, True, True, False]
            ).iloc[0]

            score_gap = weakest_selected["_score"] - best_momentum["_score"]

            if score_gap <= MOMENTUM_SOFT_INCLUDE_SCORE_GAP:
                selected = selected[selected["ticker"] != weakest_selected["ticker"]]
                selected = pd.concat([selected, best_momentum.to_frame().T], ignore_index=True)

    selected = selected.drop_duplicates("ticker", keep="first")
    remaining = ranked[~ranked["ticker"].isin(selected["ticker"])].copy()

    return selected, remaining

def score_candidates(rebalance=True, build_review=True):
    watch = normalise(read_csv_safe(WATCHLIST_PATH, BASE_COLUMNS), True)
    candidates = normalise(read_csv_safe(CANDIDATES_PATH, BASE_COLUMNS), False)

    market = read_csv_safe(MARKET_PATH)
    if not market.empty and "ticker" in market.columns:
        market["ticker"] = market["ticker"].astype(str).str.upper().str.strip()

    holdings = read_csv_safe(HOLDINGS_PATH)
    held = set()
    if not holdings.empty and "ticker" in holdings.columns:
        held = set(holdings["ticker"].astype(str).str.upper().str.strip())

    combined = pd.concat([watch, candidates], ignore_index=True)
    combined = combined.drop_duplicates("ticker", keep="first")

    scored_rows = []

    for _, row in combined.iterrows():
        price, score, trend, momentum, accel, timing_action, timing_score = score_one(row, market)

        row = row.copy()
        row["_price"] = price
        row["_score"] = score
        row["_trend_score"] = trend
        row["_momentum_score"] = momentum
        row["_accelerator_score"] = accel
        row["_timing_action"] = timing_action
        row["_timing_score"] = timing_score
        row["_tier_rank"] = tier_rank(row.get("tier", ""))
        row["_is_held"] = row["ticker"] in held

        scored_rows.append(row)

    scored = pd.DataFrame(scored_rows)

    if rebalance:
        held_rows = scored[scored["_is_held"]].copy()
        non_held = scored[~scored["_is_held"]].copy()

        active_non_held, candidate_rows = select_active_non_held(non_held)
        active = pd.concat([held_rows, active_non_held], ignore_index=True)

        active_out = []
        for _, row in active.iterrows():
            if row["_is_held"]:
                reason = f"Kept active because currently held: score {row['_score']}, timing {row['_timing_score']}"
            else:
                reason = f"Kept active top {ACTIVE_NON_HELD_LIMIT}: score {row['_score']}, timing {row['_timing_score']}"

            row = touch_review(row, reason)
            row["enabled"] = True
            active_out.append(row[BASE_COLUMNS])

        candidate_out = []
        for _, row in candidate_rows.iterrows():
            row = touch_review(
                row,
                f"Kept candidate: outside top {ACTIVE_NON_HELD_LIMIT}; score {row['_score']}, timing {row['_timing_score']}"
            )
            row["enabled"] = False
            if not str(row.get("candidate_reason", "")).strip():
                row["candidate_reason"] = "Not currently in Dashboard active watchlist"
            candidate_out.append(row[BASE_COLUMNS])

        watch = pd.DataFrame(active_out, columns=BASE_COLUMNS)
        candidates = pd.DataFrame(candidate_out, columns=BASE_COLUMNS)

        watch.to_csv(WATCHLIST_PATH, index=False)
        candidates.to_csv(CANDIDATES_PATH, index=False)
    else:
        candidates = normalise(read_csv_safe(CANDIDATES_PATH, BASE_COLUMNS), False)

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
            "last_reviewed": row.get("last_reviewed", ""),
            "review_count": row.get("review_count", 0),
            "status_reason": row.get("status_reason", ""),
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
