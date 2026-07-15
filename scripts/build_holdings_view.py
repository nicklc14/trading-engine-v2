import pandas as pd
from pathlib import Path

DATA_DIR = Path("data")

HOLDINGS_PATH = DATA_DIR / "holdings.csv"
CASH_PATH = DATA_DIR / "cash.csv"
DEPOSITS_PATH = DATA_DIR / "deposits.csv"
HOLDINGS_VIEW_PATH = DATA_DIR / "holdings_view.csv"

def read_csv_safe(path):
    if path.exists() and path.stat().st_size > 0:
        return pd.read_csv(path)
    return pd.DataFrame()

def build_holdings_view():
    holdings = read_csv_safe(HOLDINGS_PATH)
    cash = read_csv_safe(CASH_PATH)
    deposits = read_csv_safe(DEPOSITS_PATH)

    rows = []

    if not cash.empty:
        total_deposits_usd = cash.get("total_deposits_usd", pd.Series([0])).iloc[0]
        cash_available_usd = cash.get("cash_available_usd", pd.Series([0])).iloc[0]
    else:
        total_deposits_usd = 0
        cash_available_usd = 0

    total_deposits_nzd = deposits.get("amount_nzd", pd.Series(dtype=float)).sum() if not deposits.empty else 0

    rows.append({
        "section": "Cash Summary",
        "ticker": "",
        "shares": "",
        "avg_cost": "",
        "cost_basis": "",
        "current_price": "",
        "market_value": "",
        "unrealized_pnl": "",
        "holding_return_pct": "",
        "total_deposits_nzd": total_deposits_nzd,
        "total_deposits_usd": total_deposits_usd,
        "cash_available_usd": cash_available_usd,
        "notes": "Cash and deposits summary",
    })

    if not holdings.empty:
        for _, r in holdings.iterrows():
            rows.append({
                "section": "Holding",
                "ticker": r.get("ticker", ""),
                "shares": r.get("shares", ""),
                "avg_cost": r.get("avg_cost", ""),
                "cost_basis": r.get("cost_basis", ""),
                "current_price": r.get("current_price", ""),
                "market_value": r.get("market_value", ""),
                "unrealized_pnl": r.get("unrealized_pnl", ""),
                "holding_return_pct": r.get("holding_return_pct", ""),
                "total_deposits_nzd": "",
                "total_deposits_usd": "",
                "cash_available_usd": "",
                "notes": "",
            })

    out = pd.DataFrame(rows)
    out.to_csv(HOLDINGS_VIEW_PATH, index=False)
    return out

if __name__ == "__main__":
    build_holdings_view()
