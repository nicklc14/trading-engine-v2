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

def plan_why(row):
    action = clean_text(row.get("action_required"))
    tier = clean_text(row.get("tier"))
    reasons = clean_text(row.get("decision_reasons"))
    warnings = clean_text(row.get("warnings"))
    exit_reason = clean_text(row.get("exit_reason"))

    if action == "SELL":
        return f"Sell: {exit_reason or warnings}"
    if action == "TRIM":
        return f"Trim: {exit_reason}"
    if action in ["BUY", "BUY SMALL"]:
        return f"{action}: {tier}. {reasons}"
    if action == "HOLD":
        return f"Hold. {warnings or reasons}"
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

    working = signals.copy()
    if "sort_priority" not in working.columns:
        working["sort_priority"] = 99

    working = working.sort_values(
        ["sort_priority", "score", "ticker"],
        ascending=[True, False, True]
    )

    out = pd.DataFrame({
        "ticker": working.get("ticker", ""),
        "action_required": working["action_required"],
        "plan_why": working["plan_why"],
        "buy_usd": working.get("buy_amount_usd", 0),
        "sell_usd": working["sell_usd"],
        "shares_to_buy": working.get("shares_to_buy", 0),
        "shares_to_sell": working["shares_to_sell"],
        "price": working.get("price", np.nan),
        "score": working.get("score", np.nan),
        "tier": working.get("tier", ""),
        "holding_return_pct": working.get("holding_return_pct", np.nan),
        "stop_loss": working.get("stop_loss", np.nan),
        "trim_target": working.get("trim_price", np.nan),
        "risk_note": working["risk_note"],
        "position_rule": working.get("position_rule", ""),
    })

    out = out[VISIBLE_COLUMNS]
    out.to_csv(DASHBOARD_PATH, index=False)
    return out

if __name__ == "__main__":
    build_dashboard()
