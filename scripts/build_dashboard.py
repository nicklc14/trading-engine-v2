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
    if action in ["BUY", "BUY SMALL"] and "MAX" not in position_rule:
        return action
    if "ALREADY HELD" in position_rule:
        return "HOLD"
    return "WATCH"

def candidate_buy_usd(row):
    action = clean_text(row.get("action")).upper()
    blocked_by_max = "MAX" in clean_text(row.get("position_rule")).upper()

    if blocked_by_max and action in ["BUY", "BUY SMALL"]:
        return row.get("max_position_usd", 0)

    return 0

def plan_why(row):
    action = clean_text(row.get("action_required"))
    tier = clean_text(row.get("tier"))
    reasons = clean_text(row.get("decision_reasons"))
    warnings = clean_text(row.get("warnings"))
    exit_reason = clean_text(row.get("exit_reason"))
    candidate = row.get("_candidate_buy_usd", 0)

    if action == "SELL":
        return f"Sell: {exit_reason or warnings}"
    if action == "TRIM":
        return f"Trim: {exit_reason}"
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
        "sort_priority": signals.get("sort_priority", 99),
    })

    out = out.sort_values(
        ["sort_priority", "score", "ticker"],
        ascending=[True, False, True]
    )

    out = out[VISIBLE_COLUMNS]

    out.to_csv(DASHBOARD_PATH, index=False)
    return out

if __name__ == "__main__":
    build_dashboard()
