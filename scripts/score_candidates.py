import pandas as pd
import numpy as np
from pathlib import Path
from datetime import date

DATA_DIR = Path("data")

DASHBOARD_WATCHLIST_PATH = DATA_DIR / "dashboard_watchlist.csv"
CANDIDATE_POOL_PATH = DATA_DIR / "candidate_pool.csv"
MARKET_PATH = DATA_DIR / "market_data.csv"
HOLDINGS_PATH = DATA_DIR / "holdings.csv"
CANDIDATE_REVIEW_PATH = DATA_DIR / "candidate_review.csv"

ACTIVE_NON_HELD_LIMIT = 5
MOMENTUM_SOFT_INCLUDE_SCORE_GAP = 10
KEEP_SCORE = 50
REMOVE_SCORE = 40
LOW_SCORE_REVIEW_LIMIT = 3
STALE_DAYS = 14

BASE_COLUMNS = [
    "ticker", "sector", "tier", "enabled", "notes",
    "date_added", "candidate_reason",
    "last_reviewed", "review_count", "status_reason",
    "low_score_count",
]

REVIEW_COLUMNS = [
    "ticker", "recommendation", "next_up_rank", "promotion_fit", "promotion_reason",
    "tier", "score", "timing_score", "timing_action", "sector", "price",
    "trend_score", "momentum_score", "accelerator_score",
    "notes", "candidate_reason", "date_added", "days_in_pool",
    "last_reviewed", "review_count", "low_score_count",
    "stale_flag", "removal_reason", "status_reason",
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
    df["low_score_count"] = pd.to_numeric(df["low_score_count"], errors="coerce").fillna(0).astype(int)

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

def parse_date_safe(x):
    try:
        if pd.isna(x) or str(x).strip() == "":
            return None
        return pd.to_datetime(x).date()
    except Exception:
        return None

def days_since(x):
    d = parse_date_safe(x)
    if not d:
        return np.nan
    return (date.today() - d).days

def tier_rank(tier):
    tier = str(tier).upper()
    if tier == "MOONSHOT":
        return 3
    if tier == "MOMENTUM":
        return 2
    if tier == "QUALITY":
        return 1
    return 0

def touch_review(row, reason, score):
    row = row.copy()
    today = str(date.today())
    row["last_reviewed"] = today
    row["review_count"] = int(pd.to_numeric(row.get("review_count", 0), errors="coerce") or 0) + 1
    row["status_reason"] = reason

    low_count = int(pd.to_numeric(row.get("low_score_count", 0), errors="coerce") or 0)
    row["low_score_count"] = low_count + 1 if score < KEEP_SCORE else 0

    return row

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

def promotion_fit(score, timing_score, rank):
    if rank <= 3:
        return "NEXT UP"
    if score >= 70 and timing_score >= 60:
        return "STRONG CANDIDATE"
    if score >= KEEP_SCORE:
        return "MONITOR"
    return "WEAK"

def recommendation_for(score, low_score_count):
    if score < REMOVE_SCORE:
        return "REMOVE"
    if score < KEEP_SCORE and low_score_count >= LOW_SCORE_REVIEW_LIMIT:
        return "REMOVE"
    if score < KEEP_SCORE:
        return "MONITOR LOW"
    return "KEEP CANDIDATE"

def removal_reason_for(score, low_score_count):
    if score < REMOVE_SCORE:
        return f"Score below remove threshold {REMOVE_SCORE}"
    if score < KEEP_SCORE and low_score_count >= LOW_SCORE_REVIEW_LIMIT:
        return f"Score below {KEEP_SCORE} for {low_score_count} reviews"
    return ""

def score_candidates(rebalance=True, build_review=True):
    dashboard_watchlist = normalise(read_csv_safe(DASHBOARD_WATCHLIST_PATH, BASE_COLUMNS), True)
    candidate_pool = normalise(read_csv_safe(CANDIDATE_POOL_PATH, BASE_COLUMNS), False)

    market = read_csv_safe(MARKET_PATH)
    if not market.empty and "ticker" in market.columns:
        market["ticker"] = market["ticker"].astype(str).str.upper().str.strip()

    holdings = read_csv_safe(HOLDINGS_PATH)
    held = set()
    if not holdings.empty and "ticker" in holdings.columns:
        held = set(holdings["ticker"].astype(str).str.upper().str.strip())

    combined = pd.concat([dashboard_watchlist, candidate_pool], ignore_index=True)
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

            row = touch_review(row, reason, row["_score"])
            row["enabled"] = True
            active_out.append(row[BASE_COLUMNS])

        candidate_out = []
        for _, row in candidate_rows.iterrows():
            row = touch_review(
                row,
                f"Kept candidate: outside top {ACTIVE_NON_HELD_LIMIT}; score {row['_score']}, timing {row['_timing_score']}",
                row["_score"],
            )
            row["enabled"] = False
            if not str(row.get("candidate_reason", "")).strip():
                row["candidate_reason"] = "Not currently in Dashboard active watchlist"
            candidate_out.append(row[BASE_COLUMNS])

        dashboard_watchlist = pd.DataFrame(active_out, columns=BASE_COLUMNS)
        candidate_pool = pd.DataFrame(candidate_out, columns=BASE_COLUMNS)

        dashboard_watchlist.to_csv(DASHBOARD_WATCHLIST_PATH, index=False)
        candidate_pool.to_csv(CANDIDATE_POOL_PATH, index=False)
    else:
        candidate_pool = normalise(read_csv_safe(CANDIDATE_POOL_PATH, BASE_COLUMNS), False)

    if not build_review:
        return pd.DataFrame(columns=REVIEW_COLUMNS)

    review_rows = []

    scored_candidates = []
    for _, row in candidate_pool.iterrows():
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
        scored_candidates.append(row)

    scored_candidates = pd.DataFrame(scored_candidates)

    if not scored_candidates.empty:
        scored_candidates = scored_candidates.sort_values(
            ["_score", "_timing_score", "_tier_rank", "ticker"],
            ascending=[False, False, False, True]
        ).reset_index(drop=True)

    for idx, row in scored_candidates.iterrows():
        rank = idx + 1
        score = row["_score"]
        timing_score = row["_timing_score"]
        low_score_count = int(pd.to_numeric(row.get("low_score_count", 0), errors="coerce") or 0)
        days_in_pool = days_since(row.get("date_added"))
        days_since_review = days_since(row.get("last_reviewed"))

        rec = recommendation_for(score, low_score_count)
        fit = promotion_fit(score, timing_score, rank)
        removal_reason = removal_reason_for(score, low_score_count)
        stale_flag = "STALE REVIEW" if pd.notna(days_since_review) and days_since_review > STALE_DAYS else ""

        promotion_reason = (
            f"Rank {rank}; score {score}; timing {timing_score}; "
            f"tier {row.get('tier', '')}; active list limited to top {ACTIVE_NON_HELD_LIMIT}"
        )

        review_rows.append({
            "ticker": row["ticker"],
            "recommendation": rec,
            "next_up_rank": rank,
            "promotion_fit": fit,
            "promotion_reason": promotion_reason,
            "tier": row.get("tier", ""),
            "score": score,
            "timing_score": timing_score,
            "timing_action": row["_timing_action"],
            "sector": row.get("sector", ""),
            "price": row["_price"],
            "trend_score": row["_trend_score"],
            "momentum_score": row["_momentum_score"],
            "accelerator_score": row["_accelerator_score"],
            "notes": row.get("notes", ""),
            "candidate_reason": row.get("candidate_reason", row.get("notes", "")),
            "date_added": row.get("date_added", str(date.today())),
            "days_in_pool": days_in_pool,
            "last_reviewed": row.get("last_reviewed", ""),
            "review_count": row.get("review_count", 0),
            "low_score_count": low_score_count,
            "stale_flag": stale_flag,
            "removal_reason": removal_reason,
            "status_reason": row.get("status_reason", ""),
        })

    review = pd.DataFrame(review_rows, columns=REVIEW_COLUMNS)
    review.to_csv(CANDIDATE_REVIEW_PATH, index=False)
    return review

if __name__ == "__main__":
    score_candidates()
