import pandas as pd
from pathlib import Path

DATA_DIR = Path("data")

PERFORMANCE_PATH = DATA_DIR / "performance.csv"
PERFORMANCE_SUMMARY_PATH = DATA_DIR / "performance_summary.csv"

def read_csv_safe(path):
    if path.exists() and path.stat().st_size > 0:
        return pd.read_csv(path)
    return pd.DataFrame()

def build_performance_summary():
    perf = read_csv_safe(PERFORMANCE_PATH)

    if perf.empty:
        out = pd.DataFrame([{
            "metric": "status",
            "value": "No performance data available",
            "format_hint": "text",
        }])
        out.to_csv(PERFORMANCE_SUMMARY_PATH, index=False)
        return out

    r = perf.iloc[0]

    rows = [
        ("Total Deposits USD", r.get("total_deposits_usd", 0), "currency"),
        ("Cash Available USD", r.get("cash_available_usd", 0), "currency"),
        ("Holdings Value USD", r.get("holdings_value_usd", 0), "currency"),
        ("Account Equity USD", r.get("account_equity_usd", 0), "currency"),
        ("Account P&L USD", r.get("account_pnl_usd", 0), "currency"),
        ("Account Return %", r.get("account_return_pct", 0), "percent"),
        ("Realised P&L USD", r.get("realized_pnl_usd", 0), "currency"),
        ("Unrealised P&L USD", r.get("unrealized_pnl_usd", 0), "currency"),
        ("Closed Wins", r.get("closed_wins", 0), "number"),
        ("Closed Losses", r.get("closed_losses", 0), "number"),
        ("Win Rate", r.get("win_rate", 0), "percent"),
        ("Average Win USD", r.get("avg_win_usd", 0), "currency"),
        ("Average Loss USD", r.get("avg_loss_usd", 0), "currency"),
    ]

    out = pd.DataFrame([
        {"metric": metric, "value": value, "format_hint": fmt}
        for metric, value, fmt in rows
    ])

    out.to_csv(PERFORMANCE_SUMMARY_PATH, index=False)
    return out

if __name__ == "__main__":
    build_performance_summary()
