import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path("data")

SIGNALS_PATH = DATA_DIR / "signals.csv"
HOLDINGS_PATH = DATA_DIR / "holdings.csv"
DASHBOARD_PATH = DATA_DIR / "dashboard.csv"

def clean_text(x):
    if pd.isna(x):
        return ""
    return str(x).strip()

def action_required(row):
    exit_action = clean_text(row.get("exit_action")).upper()
    action = clean_text(row.get("action")).upper()
    position_rule = clean_text(row.get("position_rule")).upper()

    if exit_action == "SELL":
        return "SELL"
    if exit_action == "TRIM":
        return "TRIM"
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
    add_more = clean_text(row.get("add_more_reason"))

    if action == "SELL":
        return f"Sell/exit: {exit_reason or warnings}"
    if action == "TRIM":
        return f"Trim: {exit_reason}"
    if action in ["BUY", "BUY SMALL"]:
        return f"{action}: {tier}. {reasons}"
    if action == "HOLD":
        if warnings:
            return f"Hold. {warnings}"
        if add_more:
            return f"Hold. {add_more}"
        return "Hold current position."
    return warnings or reasons or "Watch only."

def sell_usd(row):
    action = clean_text(row.get("action_required"))
    market_value = row.get("market_value", np.nan)

    if action == "SELL" and pd.notna(market_value):
        return market_value
    if action == "TRIM" and pd.notna(market_value):
        return market_value * 0.25
    return 0

def risk_note(row):
    tier = clean_text(row.get("tier")).upper()
    warnings = clean_text(row.get("warnings"))
    stop = row.get("stop_loss", np.nan)
    trim = row.get("trim_price", np.nan)

    parts = []
    if tier == "MOONSHOT":
        parts.append("Moonshot: high risk / small size")
    if warnings:
        parts.append(warnings)
    if pd.notna(stop):
        parts.append(f"Stop {stop:.2f}")
    if pd.notna(trim):
        parts.append(f"Trim {trim:.2f}")
    return " | ".join(parts)

def build_dashboard():
    signals = pd.read_csv(SIGNALS_PATH)
    holdings = pd.read_csv(HOLDINGS_PATH) if HOLDINGS_PATH.exists() else pd.DataFrame()

    if not holdings.empty:
        holdings["ticker"] = holdings["ticker"].astype(str).str.upper().str.strip()
        keep = ["ticker", "market_value"]
        holdings = holdings[[c for c in keep if c in holdings.columns]]
        signals = signals.merge(holdings, on="ticker", how="left")
    else:
        signals["market_value"] = np.nan

    signals["action_required"] = signals.apply(action_required, axis=1)
    signals["plan_why"] = signals.apply(plan_why, axis=1)
    signals["sell_usd"] = signals.apply(sell_usd, axis=1)
    signals["risk_note"] = signals.apply(risk_note, axis=1)

    out = pd.DataFrame({
        "ticker": signals.get("ticker", ""),
        "action_required": signals["action_required"],
        "plan_why": signals["plan_why"],
        "buy_usd": signals.get("buy_amount_usd", 0),
        "sell_usd": signals["sell_usd"],
        "shares_to_buy": signals.get("shares_to_buy", 0),
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

    out.to_csv(DASHBOARD_PATH, index=False)
    return out

if __name__ == "__main__":
    build_dashboard()
