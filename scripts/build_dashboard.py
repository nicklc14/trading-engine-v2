import pandas as pd
from pathlib import Path

DATA_DIR = Path("data")

SIGNALS_PATH = DATA_DIR / "signals.csv"
PREMARKET_PATH = DATA_DIR / "premarket_signals.csv"
DASHBOARD_PATH = DATA_DIR / "dashboard.csv"

DASHBOARD_COLUMNS = [
    "ticker",
    "action",
    "score",
    "tier",
    "price",
    "buy_amount_usd",
    "shares_to_buy",
    "exit_action",
    "exit_priority",
    "exit_reason",
    "position_rule",
    "holding_return_pct",
    "stop_loss",
    "trim_price",
    "warnings",
    "decision_reasons",
]

def build_dashboard():
    signals = pd.read_csv(SIGNALS_PATH)

    if PREMARKET_PATH.exists():
        pre = pd.read_csv(PREMARKET_PATH)
        pre_cols = ["ticker", "premarket_score", "premarket_action"]
        pre = pre[[c for c in pre_cols if c in pre.columns]]
        signals = signals.merge(pre, on="ticker", how="left")

    for col in DASHBOARD_COLUMNS:
        if col not in signals.columns:
            signals[col] = ""

    out = signals[DASHBOARD_COLUMNS].copy()

    out.to_csv(DASHBOARD_PATH, index=False)
    return out

if __name__ == "__main__":
    build_dashboard()
