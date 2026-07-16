import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path("data")
SIGNALS_PATH = DATA_DIR / "signals.csv"
HOLDINGS_PATH = DATA_DIR / "holdings.csv"
CASH_PATH = DATA_DIR / "cash.csv"
MARKET_TIMING_PATH = DATA_DIR / "market_timing.csv"
DATA_QUALITY_PATH = DATA_DIR / "data_quality_report.csv"
DASHBOARD_PATH = DATA_DIR / "dashboard.csv"

REPLACEMENT_HELD_SCORE_MAX = 60
REPLACEMENT_SCORE_GAP = 20

VISIBLE_COLUMNS = [
    "ticker", "action_required", "position_rule", "plan_why",
    "buy_usd", "sell_usd", "shares_to_buy", "shares_to_sell",
    "price", "score", "tier", "holding_return_pct",
    "stop_loss", "trim_target", "risk_note", "add_more",
]

def clean_text(x):
    return "" if pd.isna(x) else str(x).strip()

def get_cash_available():
    if not CASH_PATH.exists():
        return 0.0
    cash = pd.read_csv(CASH_PATH)
    if cash.empty or "cash_available_usd" not in cash.columns:
        return 0.0
    val = pd.to_numeric(cash["cash_available_usd"].iloc[0], errors="coerce")
    return 0.0 if pd.isna(val) else float(val)

def load_market_timing():
    if not MARKET_TIMING_PATH.exists():
        return pd.DataFrame(columns=["ticker", "timing_action", "timing_score", "position_rationale"])

    timing = pd.read_csv(MARKET_TIMING_PATH)
    if timing.empty:
        return pd.DataFrame(columns=["ticker", "timing_action", "timing_score", "position_rationale"])

    timing["ticker"] = timing["ticker"].astype(str).str.upper().str.strip()
    keep = [c for c in [
        "ticker", "timing_action", "timing_score", "position_rationale",
        "reason_tags", "data_note"
    ] if c in timing.columns]

    return timing[keep]

def load_data_quality():
    if not DATA_QUALITY_PATH.exists():
        return {}, "UNKNOWN"

    dq = pd.read_csv(DATA_QUALITY_PATH)
    if dq.empty or "severity" not in dq.columns:
        return {}, "UNKNOWN"

    severity_rank = {"OK": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}
    ticker_status = {}
    global_status = "OK"

    for _, row in dq.iterrows():
        ticker = clean_text(row.get("ticker")).upper()
        severity = clean_text(row.get("severity")).upper()
        issue = clean_text(row.get("issue"))

        if severity not in severity_rank:
            continue

        if severity_rank[severity] > severity_rank.get(global_status, 0):
            global_status = severity

        if ticker:
            old = ticker_status.get(ticker, {"severity": "OK", "issues": []})
            if severity_rank[severity] > severity_rank.get(old["severity"], 0):
                old["severity"] = severity
            if issue:
                old["issues"].append(issue)
            ticker_status[ticker] = old

    return ticker_status, global_status

def base_action_required(row):
    exit_action = clean_text(row.get("exit_action")).upper()
    action = clean_text(row.get("action")).upper()
    position_rule = clean_text(row.get("position_rule")).upper()

    if exit_action in ["SELL", "TRIM"]:
        return exit_action
    if "ALREADY HELD" in position_rule:
        return "HOLD"
    if action in ["BUY", "BUY SMALL"] and "MAX" not in position_rule:
        return action
    return "WATCH"

def validate_action(row):
    action = clean_text(row.get("_base_action")).upper()
    timing = clean_text(row.get("timing_action")).upper()
    dq_severity = clean_text(row.get("_data_quality_severity")).upper()

    if action in ["SELL", "TRIM", "HOLD"]:
        return action
    if dq_severity == "HIGH":
        return "WATCH"
    if action in ["BUY", "BUY SMALL"]:
        if timing == "TIMING CONFIRMED":
            return action
        if timing == "TIMING WATCH":
            return "BUY SMALL"
        return "WATCH"
    return action

def add_more(row):
    base_action = clean_text(row.get("_base_action")).upper()
    final_action = clean_text(row.get("action_required")).upper()
    signal = clean_text(row.get("add_more_signal")).upper()
    timing = clean_text(row.get("timing_action")).upper()
    dq_severity = clean_text(row.get("_data_quality_severity")).upper()

    if base_action == "HOLD" and final_action == "HOLD" and signal == "ADD SMALL":
        if dq_severity == "HIGH":
            return ""
        if timing in ["TIMING CONFIRMED", "TIMING WATCH"]:
            return "ADD SMALL"
    return ""

def dashboard_priority(row):
    action = clean_text(row.get("action_required")).upper()
    add_signal = clean_text(row.get("add_more")).upper()
    replacement = clean_text(row.get("_replacement_note"))
    exit_priority = clean_text(row.get("exit_priority")).upper()
    score = pd.to_numeric(row.get("score", 0), errors="coerce")

    if action == "SELL" and exit_priority == "HIGH":
        return 1
    if action == "SELL":
        return 2
    if action == "TRIM":
        return 3
    if replacement:
        return 4
    if add_signal == "ADD SMALL":
        return 5
    if action == "HOLD":
        return 6
    if action == "BUY":
        return 7
    if action == "BUY SMALL":
        return 8
    if action == "WATCH" and pd.notna(score) and score >= 80:
        return 9
    return 10

def timing_note(row):
    timing = clean_text(row.get("timing_action")).upper()
    timing_score = row.get("timing_score", np.nan)

    if timing == "TIMING CONFIRMED":
        return f"Timing confirmed ({timing_score:.0f})" if pd.notna(timing_score) else "Timing confirmed"
    if timing == "TIMING WATCH":
        return f"Timing watch ({timing_score:.0f})" if pd.notna(timing_score) else "Timing watch"
    if timing == "WAIT":
        return f"Timing not confirmed ({timing_score:.0f})" if pd.notna(timing_score) else "Timing not confirmed"
    return "Timing unavailable"

def quality_note(row):
    severity = clean_text(row.get("_data_quality_severity")).upper()
    issues = row.get("_data_quality_issues", "")

    if severity in ["", "OK"]:
        return "Data quality OK"
    if issues:
        return f"Data quality {severity}: {issues}"
    return f"Data quality {severity}"

def watchlist_review_note(row):
    action = clean_text(row.get("action_required")).upper()
    tier = clean_text(row.get("tier")).upper()
    score = pd.to_numeric(row.get("score", np.nan), errors="coerce")
    timing = clean_text(row.get("timing_action")).upper()

    if action != "WATCH":
        return ""
    if pd.notna(score) and score < 40:
        return "Review watchlist — low score and weak setup"
    if tier == "QUALITY" and (pd.isna(score) or score < 60):
        return "Review watchlist — QUALITY name may not fit high-return momentum/moonshot focus"
    if timing == "WAIT" and pd.notna(score) and score < 60:
        return "Review watchlist — weak timing and weak signal"
    return ""

def add_replacement_notes(signals):
    signals["_replacement_note"] = ""

    non_held = signals[
        ~signals["position_rule"].astype(str).str.upper().str.contains("ALREADY HELD", na=False)
    ].copy()

    if non_held.empty:
        return signals

    non_held["_score_num"] = pd.to_numeric(non_held["score"], errors="coerce")
    non_held = non_held.dropna(subset=["_score_num"])

    if non_held.empty:
        return signals

    best = non_held.sort_values(["_score_num", "ticker"], ascending=[False, True]).iloc[0]
    best_ticker = best["ticker"]
    best_score = best["_score_num"]
    best_tier = clean_text(best.get("tier"))

    for idx, row in signals.iterrows():
        is_held = "ALREADY HELD" in clean_text(row.get("position_rule")).upper()
        if not is_held:
            continue

        held_score = pd.to_numeric(row.get("score"), errors="coerce")
        held_return = pd.to_numeric(row.get("holding_return_pct"), errors="coerce")
        held_tier = clean_text(row.get("tier")).upper()

        if pd.isna(held_score):
            continue

        protect_strong_moonshot = held_tier == "MOONSHOT" and held_score >= 75

        if (
            held_score < REPLACEMENT_HELD_SCORE_MAX
            and best_score >= held_score + REPLACEMENT_SCORE_GAP
            and (pd.isna(held_return) or held_return <= 0)
            and not protect_strong_moonshot
        ):
            signals.at[idx, "_replacement_note"] = (
                f"Replacement review: {best_ticker} ({best_tier}, score {best_score:.0f}) "
                f"is much stronger than held score {held_score:.0f}."
            )

    return signals

def build_plan_why(row):
    action = clean_text(row.get("action_required"))
    base_action = clean_text(row.get("_base_action"))
    add_signal = clean_text(row.get("add_more"))
    tier = clean_text(row.get("tier"))
    reasons = clean_text(row.get("decision_reasons"))
    warnings = clean_text(row.get("warnings"))
    exit_reason = clean_text(row.get("exit_reason"))
    add_reason = clean_text(row.get("add_more_reason"))
    replacement = clean_text(row.get("_replacement_note"))
    buy_usd = pd.to_numeric(row.get("buy_usd", 0), errors="coerce")
    timing = timing_note(row)
    quality = quality_note(row)
    review_note = watchlist_review_note(row)

    suffix = f" {replacement}" if replacement else ""

    if action == "SELL":
        return f"Sell: {exit_reason or warnings}. {quality}{suffix}"
    if action == "TRIM":
        return f"Trim: {exit_reason}. {quality}{suffix}"
    if add_signal == "ADD SMALL":
        return f"Add small ${buy_usd:.2f}: {add_reason}. {timing}. {quality}. {reasons}{suffix}"
    if action in ["BUY", "BUY SMALL"]:
        return f"{action} ${buy_usd:.2f}: {tier}. {timing}. {quality}. {reasons}{suffix}"
    if action == "HOLD":
        if add_reason:
            return f"Hold. {add_reason}. {timing}. {quality}. {warnings or reasons}{suffix}"
        return f"Hold. {timing}. {quality}. {warnings or reasons}{suffix}"
    if base_action in ["BUY", "BUY SMALL"] and action == "WATCH":
        return f"Wait — signal was {base_action}, but not trade-ready. {timing}. {quality}. {warnings or reasons}{suffix}"
    if review_note:
        return f"{review_note}. {timing}. {quality}. {warnings or reasons}{suffix}"
    return f"{timing}. {quality}. {warnings or reasons or 'Watch only.'}{suffix}"

def build_risk_note(row):
    warnings = clean_text(row.get("warnings"))
    replacement = clean_text(row.get("_replacement_note"))
    stop = pd.to_numeric(row.get("stop_loss", np.nan), errors="coerce")
    timing = timing_note(row)
    quality = quality_note(row)

    parts = []
    if warnings:
        parts.append(warnings)
    if replacement:
        parts.append(replacement)
    parts.append(timing)
    parts.append(quality)
    if pd.notna(stop):
        parts.append(f"Stop {stop:.2f}")

    return " | ".join([p for p in parts if p])

def allocate_cash(signals):
    remaining_cash = get_cash_available()

    signals["buy_usd"] = 0.0
    signals["shares_to_buy"] = 0.0
    signals["_dashboard_priority"] = signals.apply(dashboard_priority, axis=1)

    candidates = signals[
        (signals["action_required"].isin(["BUY", "BUY SMALL"]))
        | (signals["add_more"] == "ADD SMALL")
    ].copy()

    candidates = candidates.sort_values(
        ["_dashboard_priority", "score", "ticker"],
        ascending=[True, False, True]
    )

    for idx, row in candidates.iterrows():
        if remaining_cash <= 0:
            break

        price = pd.to_numeric(row.get("price", np.nan), errors="coerce")
        suggested_cap = pd.to_numeric(row.get("buy_amount_usd", 0), errors="coerce")

        if pd.isna(price) or price <= 0 or pd.isna(suggested_cap) or suggested_cap <= 0:
            continue

        if row.get("_base_action") == "BUY" and row.get("action_required") == "BUY SMALL":
            suggested_cap *= 0.5

        allocation = min(suggested_cap, remaining_cash)

        signals.at[idx, "buy_usd"] = round(allocation, 2)
        signals.at[idx, "shares_to_buy"] = round(allocation / price, 6)

        remaining_cash -= allocation

    return signals

def build_dashboard():
    signals = pd.read_csv(SIGNALS_PATH)

    holdings = pd.read_csv(HOLDINGS_PATH) if HOLDINGS_PATH.exists() else pd.DataFrame()
    timing = load_market_timing()
    dq_status, global_dq = load_data_quality()

    signals["ticker"] = signals["ticker"].astype(str).str.upper().str.strip()

    if not timing.empty:
        signals = signals.merge(timing, on="ticker", how="left")
    else:
        signals["timing_action"] = ""
        signals["timing_score"] = np.nan
        signals["position_rationale"] = ""

    if not holdings.empty:
        holdings["ticker"] = holdings["ticker"].astype(str).str.upper().str.strip()
        keep = [c for c in ["ticker", "market_value", "shares"] if c in holdings.columns]
        signals = signals.merge(holdings[keep], on="ticker", how="left")
    else:
        signals["market_value"] = np.nan
        signals["shares"] = np.nan

    signals["_data_quality_severity"] = signals["ticker"].apply(
        lambda t: dq_status.get(t, {"severity": global_dq}).get("severity", global_dq)
    )
    signals["_data_quality_issues"] = signals["ticker"].apply(
        lambda t: "; ".join(dq_status.get(t, {"issues": []}).get("issues", []))
    )

    signals["_base_action"] = signals.apply(base_action_required, axis=1)
    signals["action_required"] = signals.apply(validate_action, axis=1)
    signals["add_more"] = signals.apply(add_more, axis=1)

    signals = allocate_cash(signals)
    signals = add_replacement_notes(signals)

    signals["sell_usd"] = np.where(
        signals["action_required"] == "SELL",
        signals.get("market_value", 0),
        np.where(signals["action_required"] == "TRIM", signals.get("market_value", 0) * 0.25, 0)
    )

    signals["shares_to_sell"] = np.where(
        signals["action_required"] == "SELL",
        signals.get("shares", 0),
        np.where(signals["action_required"] == "TRIM", signals.get("shares", 0) * 0.25, 0)
    )

    signals["plan_why"] = signals.apply(build_plan_why, axis=1)
    signals["risk_note"] = signals.apply(build_risk_note, axis=1)
    signals["_dashboard_priority"] = signals.apply(dashboard_priority, axis=1)

    out = pd.DataFrame({
        "ticker": signals.get("ticker", ""),
        "action_required": signals["action_required"],
        "position_rule": signals.get("position_rule", ""),
        "plan_why": signals["plan_why"],
        "buy_usd": signals["buy_usd"],
        "sell_usd": signals["sell_usd"],
        "shares_to_buy": signals["shares_to_buy"],
        "shares_to_sell": signals["shares_to_sell"],
        "price": signals.get("price", np.nan),
        "score": signals.get("score", np.nan),
        "tier": signals.get("tier", ""),
        "holding_return_pct": signals.get("holding_return_pct", np.nan),
        "stop_loss": signals.get("stop_loss", np.nan),
        "trim_target": signals.get("trim_price", np.nan),
        "risk_note": signals["risk_note"],
        "add_more": signals["add_more"],
        "_dashboard_priority": signals["_dashboard_priority"],
    })

    out = out.sort_values(
        ["_dashboard_priority", "score", "ticker"],
        ascending=[True, False, True]
    )

    out = out[VISIBLE_COLUMNS]
    out.to_csv(DASHBOARD_PATH, index=False)
    return out

if __name__ == "__main__":
    build_dashboard()
