import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path("data")
SIGNALS_PATH = DATA_DIR / "signals.csv"
HOLDINGS_PATH = DATA_DIR / "holdings.csv"
DASHBOARD_PATH = DATA_DIR / "dashboard.csv"

VISIBLE_COLUMNS = [
    "ticker",
    "action_required",
    "add_more",
    "plan_why",
    "buy_usd",
    "sell_usd",
    "shares_to_buy",
    "shares_to_sell",
    "price",
    "score",
    "tier",
    "holding_return_pct",
    "stop_loss",
    "trim_target",
    "risk_note",
    "position_rule",
]

def clean_text(x):
    return "" if pd.isna(x) else str(x).strip()

def action_required(row):
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

def add_more(row):
    action = clean_text(row.get("action_required")).upper()
    signal = clean_text(row.get("add_more_signal")).upper()

    if action == "HOLD" and signal == "ADD SMALL":
        return "ADD SMALL"

    return ""

def dashboard_priority(row):
    action = clean_text(row.get("action_required")).upper()
    add_signal = clean_text(row.get("add_more")).upper()
    exit_priority = clean_text(row.get("exit_priority")).upper()
    score = pd.to_numeric(row.get("score", 0), errors="coerce")

    if action == "SELL" and exit_priority == "HIGH":
        return 1
    if action == "SELL":
        return 2
    if action == "TRIM":
        return 3
    if add_signal == "ADD SMALL":
        return 4
    if action == "HOLD":
        return 5
    if action == "BUY":
        return 6
    if action == "BUY SMALL":
        return 7
    if action == "WATCH" and pd.notna(score) and score >= 80:
        return 8
    return 9

def candidate_buy_usd(row):
    action = clean_text(row.get("action")).upper()
    blocked_by_max = "MAX" in clean_text(row.get("position_rule")).upper()

    if blocked_by_max and action in ["BUY", "BUY SMALL"]:
        return row.get("max_position_usd", 0)

    return 0

def plan_why(row):
    action = clean_text(row.get("action_required"))
    add_signal = clean_text(row.get("add_more"))
    tier = clean_text(row.get("tier"))
    reasons = clean_text(row.get("decision_reasons"))
    warnings = clean_text(row.get("warnings"))
    exit_reason = clean_text(row.get("exit_reason"))
    add_reason = clean_text(row.get("add_more_reason"))
    candidate = row.get("_candidate_buy_usd", 0)

    if action == "SELL":
        return f"Sell: {exit_reason or warnings}"
    if action == "TRIM":
        return f"Trim: {exit_reason}"
    if add_signal == "ADD SMALL":
        return f"Add small: {add_reason}. {reasons}"
    if action in ["BUY", "BUY SMALL"]:
        return f"{action}: {tier}. {reasons}"
    if action == "HOLD":
        return f"Hold. {warnings or reasons}"
    if candidate and candidate > 0:
        return f"Watch only — max positions reached. Candidate if slot frees: ${candidate:.2f}. {reasons or warnings}"
    return warnings or reasons or "Watch only."

def build_dashboard():
    signals = pd.read_csv(SIGNALS_PATH)
    holdings = pd.read_csv(HOLDINGS_PATH) if HOLDINGS_PATH.exists() else pd.DataFrame()

    if not holdings.empty:
        holdings["ticker"] = holdings["ticker"].astype(str).str.upper().str.strip()
        keep = [c for c in ["ticker", "market_value", "shares"] if c in holdings.columns]
        holdings = holdings[keep]
        signals = signals.merge(holdings, on="ticker", how="left")
    else:
        signals["market_value"] = np.nan
        signals["shares"] = np.nan

    signals["action_required"] = signals.apply(action_required, axis=1)
    signals["add_more"] = signals.apply(add_more, axis=1)
    signals["_candidate_buy_usd"] = signals.apply(candidate_buy_usd, axis=1)
    signals["plan_why"] = signals.apply(plan_why, axis=1)

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

    signals["risk_note"] = (
        signals.get("warnings", "").fillna("").astype(str)
        + " | Stop "
        + pd.to_numeric(signals.get("stop_loss", np.nan), errors="coerce").round(2).astype(str)
    )

    out = pd.DataFrame({
        "ticker": signals.get("ticker", ""),
        "action_required": signals["action_required"],
        "add_more": signals["add_more"],
        "plan_why": signals["plan_why"],
        "buy_usd": signals.get("buy_amount_usd", 0),
        "sell_usd": signals["sell_usd"],
        "shares_to_buy": signals.get("shares_to_buy", 0),
        "shares_to_sell": signals["shares_to_sell"],
        "price": signals.get("price", np.nan),
        "score": signals.get("score", np.nan),
        "tier": signals.get("tier", ""),
        "holding_return_pct": signals.get("holding_return_pct", np.nan),
        "stop_loss": signals.get("stop_loss", np.nan),
        "trim_target": signals.get("trim_price", np.nan),
        "risk_note": signals["risk_note"],
        "position_rule": signals.get("position_rule", ""),
        "exit_priority": signals.get("exit_priority", ""),
    })

    out["_dashboard_priority"] = out.apply(dashboard_priority, axis=1)

    out = out.sort_values(
        ["_dashboard_priority", "score", "ticker"],
        ascending=[True, False, True]
    )

    out = out[VISIBLE_COLUMNS]

    out.to_csv(DASHBOARD_PATH, index=False)
    return out

if __name__ == "__main__":
    build_dashboard()
