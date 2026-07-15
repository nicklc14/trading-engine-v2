import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timezone

DATA_DIR = Path("data")

WATCHLIST_PATH = DATA_DIR / "watchlist.csv"
CANDIDATE_PATH = DATA_DIR / "candidate_watchlist.csv"
MARKET_PATH = DATA_DIR / "market_data.csv"
HOLDINGS_PATH = DATA_DIR / "holdings.csv"
CANDIDATE_REVIEW_PATH = DATA_DIR / "candidate_review.csv"

WATCHLIST_COLUMNS = ["ticker", "sector", "tier", "enabled", "notes"]
CANDIDATE_COLUMNS = ["ticker", "sector", "tier", "enabled", "notes", "date_added", "candidate_reason"]

def truthy(x):
    return str(x).strip().upper() in ["TRUE", "YES", "1", "Y"]

def clamp(x, lo=0, hi=100):
    return max(lo, min(hi, x))

def ensure_columns(df, columns):
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    return df[columns]

def score_market_row(row):
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
    timing_score = 50
    gap_pct = row.get("gap_pct", np.nan)
    volume_trend = row.get("volume_trend", np.nan)
    macd_hist = row.get("macd_histogram", np.nan)
    rsi = row.get("rsi_14", np.nan)

    if pd.notna(gap_pct):
        if gap_pct > 0.05:
            timing_score += 25
        elif gap_pct > 0.03:
            timing_score += 15
        elif gap_pct < -0.03:
            timing_score -= 30

    if pd.notna(volume_trend):
        if volume_trend >= 2.0:
            timing_score += 25
        elif volume_trend >= 1.5:
            timing_score += 15
        elif volume_trend < 0.7:
            timing_score -= 15

    if pd.notna(macd_hist):
        timing_score += 10 if macd_hist > 0 else -10

    if pd.notna(rsi):
        if 40 <= rsi <= 70:
            timing_score += 10
        elif rsi > 80 or rsi < 30:
            timing_score -= 15

    timing_score = clamp(round(timing_score))

    if timing_score >= 80:
        return "TIMING CONFIRMED", timing_score
    if timing_score >= 70:
        return "TIMING WATCH", timing_score
    return "WAIT", timing_score

def candidate_recommendation(tier, score, trend_score, momentum_score, timing):
    tier = str(tier).upper()

    if score >= 80 and trend_score >= 70 and timing in ["TIMING CONFIRMED", "TIMING WATCH"]:
        return "PROMOTE", "Strong enough for active watchlist"

    if tier in ["MOMENTUM", "MOONSHOT"] and score >= 70 and momentum_score >= 60:
        return "KEEP CANDIDATE", "Interesting but not ready"

    if score < 40:
        return "REMOVE", "Low score and weak setup"

    return "KEEP CANDIDATE", "Monitor for improvement"

def active_recommendation(ticker, tier, score, momentum_score, timing, held_tickers):
    tier = str(tier).upper()

    if ticker in held_tickers:
        return "KEEP ACTIVE", "Currently held — keep active until sold"

    if score >= 50:
        return "KEEP ACTIVE", "Still strong enough for active monitoring"

    if timing in ["TIMING CONFIRMED", "TIMING WATCH"]:
        return "KEEP ACTIVE", "Timing still worth monitoring"

    if tier in ["MOMENTUM", "MOONSHOT"] and momentum_score >= 60:
        return "KEEP ACTIVE", "Momentum/moonshot still developing"

    if tier == "QUALITY" and score < 35:
        return "REMOVE WATCHLIST", "Low score and does not fit high-return focus"

    if score < 40 and timing == "WAIT":
        return "DEMOTE WATCHLIST", "Weak active setup — move to candidates"

    return "KEEP ACTIVE", "No demotion rule triggered"

def score_candidates():
    today = datetime.now(timezone.utc).date().isoformat()

    watch = pd.read_csv(WATCHLIST_PATH) if WATCHLIST_PATH.exists() else pd.DataFrame(columns=WATCHLIST_COLUMNS)
    candidates = pd.read_csv(CANDIDATE_PATH) if CANDIDATE_PATH.exists() else pd.DataFrame(columns=CANDIDATE_COLUMNS)
    market = pd.read_csv(MARKET_PATH) if MARKET_PATH.exists() else pd.DataFrame()
    holdings = pd.read_csv(HOLDINGS_PATH) if HOLDINGS_PATH.exists() else pd.DataFrame()

    watch = ensure_columns(watch, WATCHLIST_COLUMNS)
    candidates = ensure_columns(candidates, CANDIDATE_COLUMNS)

    watch.to_csv(DATA_DIR / "watchlist_before_rebalance.csv", index=False)
    candidates.to_csv(DATA_DIR / "candidate_watchlist_before_rebalance.csv", index=False)

    watch["ticker"] = watch["ticker"].astype(str).str.upper().str.strip()
    candidates["ticker"] = candidates["ticker"].astype(str).str.upper().str.strip()

    market_map = {}
    if not market.empty and "ticker" in market.columns:
        market["ticker"] = market["ticker"].astype(str).str.upper().str.strip()
        market_map = {r["ticker"]: r for _, r in market.iterrows()}

    held_tickers = set()
    if not holdings.empty and "ticker" in holdings.columns:
        held_tickers = set(holdings["ticker"].astype(str).str.upper().str.strip())

    active_tickers = set(watch.loc[watch["enabled"].apply(truthy), "ticker"])

    new_watch_rows = []
    new_candidate_rows = []
    review_rows = []

    # Rebalance active watchlist, but do not write active rows to candidate_review.
    for _, row in watch.iterrows():
        ticker = row["ticker"]
        enabled = truthy(row.get("enabled", True))

        market_row = market_map.get(ticker, {})
        score, trend_score, momentum_score, accelerator_score = score_market_row(market_row)
        timing, timing_score = timing_action(market_row)

        if enabled:
            rec, why = active_recommendation(
                ticker, row.get("tier", ""), score, momentum_score, timing, held_tickers
            )
        else:
            rec, why = "DISABLED", "Already disabled in active watchlist"

        if rec == "DEMOTE WATCHLIST":
            new_candidate_rows.append({
                "ticker": ticker,
                "sector": row.get("sector", ""),
                "tier": row.get("tier", ""),
                "enabled": "TRUE",
                "notes": row.get("notes", ""),
                "date_added": today,
                "candidate_reason": "Auto-demoted from active watchlist",
            })
        elif rec == "REMOVE WATCHLIST":
            new_candidate_rows.append({
                "ticker": ticker,
                "sector": row.get("sector", ""),
                "tier": row.get("tier", ""),
                "enabled": "FALSE",
                "notes": row.get("notes", ""),
                "date_added": today,
                "candidate_reason": "Auto-removed from active watchlist",
            })
        else:
            new_watch_rows.append({
                "ticker": ticker,
                "sector": row.get("sector", ""),
                "tier": row.get("tier", ""),
                "enabled": row.get("enabled", "TRUE"),
                "notes": row.get("notes", ""),
            })

    # Rebalance candidates and write only candidates to candidate_review.
    current_active = set([r["ticker"] for r in new_watch_rows])

    for _, row in candidates.iterrows():
        ticker = row["ticker"]

        if not ticker or ticker == "NAN":
            continue

        if ticker in current_active:
            # Keep lists clean: do not keep duplicates in candidates.
            continue

        enabled = truthy(row.get("enabled", True))
        market_row = market_map.get(ticker, {})
        score, trend_score, momentum_score, accelerator_score = score_market_row(market_row)
        timing, timing_score = timing_action(market_row)

        if enabled:
            rec, why = candidate_recommendation(
                row.get("tier", ""), score, trend_score, momentum_score, timing
            )
        else:
            rec, why = "DISABLED", "Candidate disabled"

        review_rows.append({
            "ticker": ticker,
            "source_list": "CANDIDATE",
            "sector": row.get("sector", ""),
            "tier": row.get("tier", ""),
            "price": market_row.get("price", np.nan),
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

        if rec == "PROMOTE":
            new_watch_rows.append({
                "ticker": ticker,
                "sector": row.get("sector", ""),
                "tier": row.get("tier", ""),
                "enabled": "TRUE",
                "notes": row.get("notes", ""),
            })
        elif rec == "REMOVE":
            new_candidate_rows.append({
                "ticker": ticker,
                "sector": row.get("sector", ""),
                "tier": row.get("tier", ""),
                "enabled": "FALSE",
                "notes": row.get("notes", ""),
                "date_added": row.get("date_added", today),
                "candidate_reason": row.get("candidate_reason", ""),
            })
        else:
            new_candidate_rows.append({
                "ticker": ticker,
                "sector": row.get("sector", ""),
                "tier": row.get("tier", ""),
                "enabled": row.get("enabled", "TRUE"),
                "notes": row.get("notes", ""),
                "date_added": row.get("date_added", today),
                "candidate_reason": row.get("candidate_reason", ""),
            })

    new_watch = pd.DataFrame(new_watch_rows).drop_duplicates("ticker", keep="first")
    new_candidates = pd.DataFrame(new_candidate_rows).drop_duplicates("ticker", keep="first")
    review = pd.DataFrame(review_rows)

    new_watch = ensure_columns(new_watch, WATCHLIST_COLUMNS)
    new_candidates = ensure_columns(new_candidates, CANDIDATE_COLUMNS)

    if review.empty:
        review = pd.DataFrame([{
            "ticker": "",
            "source_list": "CANDIDATE",
            "sector": "",
            "tier": "",
            "price": np.nan,
            "score": np.nan,
            "trend_score": np.nan,
            "momentum_score": np.nan,
            "accelerator_score": np.nan,
            "timing_action": "",
            "timing_score": np.nan,
            "recommendation": "NO CANDIDATES",
            "why": "No non-active candidate tickers to review",
            "notes": "",
            "date_added": "",
            "candidate_reason": "",
        }])

    new_watch.to_csv(WATCHLIST_PATH, index=False)
    new_candidates.to_csv(CANDIDATE_PATH, index=False)
    review.to_csv(CANDIDATE_REVIEW_PATH, index=False)

    return review

if __name__ == "__main__":
    score_candidates()
