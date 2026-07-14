import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path("data")
TRADES_PATH = DATA_DIR / "trades.csv"
MARKET_PATH = DATA_DIR / "market_data.csv"
HOLDINGS_PATH = DATA_DIR / "holdings.csv"

def calculate_holdings():
    if not TRADES_PATH.exists():
        pd.DataFrame().to_csv(HOLDINGS_PATH, index=False)
        return pd.DataFrame()

    trades = pd.read_csv(TRADES_PATH)

    if trades.empty:
        pd.DataFrame().to_csv(HOLDINGS_PATH, index=False)
        return pd.DataFrame()

    market = pd.read_csv(MARKET_PATH) if MARKET_PATH.exists() else pd.DataFrame()
    price_map = dict(zip(market.get("ticker", []), market.get("price", [])))

    rows = []

    for ticker, g in trades.groupby("ticker"):
        ticker = str(ticker).upper()

        if ticker in ["CASH", "DEPOSIT"]:
            continue

        g["type_upper"] = g["type"].astype(str).str.upper()

        buys = g[g["type_upper"] == "BUY"]
        sells = g[g["type_upper"] == "SELL"]

        buy_shares = buys["shares"].sum()
        sell_shares = sells["shares"].sum()
        shares = buy_shares - sell_shares

        if shares <= 0:
            continue

        buy_cost = buys["value"].sum() + buys["transaction_fee"].fillna(0).sum()
        avg_cost = buy_cost / buy_shares if buy_shares > 0 else np.nan

        current_price = price_map.get(ticker, np.nan)
        market_value = shares * current_price if pd.notna(current_price) else np.nan
        cost_basis = shares * avg_cost if pd.notna(avg_cost) else np.nan
        unrealized_pnl = market_value - cost_basis if pd.notna(market_value) and pd.notna(cost_basis) else np.nan
        holding_return_pct = unrealized_pnl / cost_basis if pd.notna(unrealized_pnl) and cost_basis > 0 else np.nan

        rows.append({
            "ticker": ticker,
            "shares": shares,
            "avg_cost": avg_cost,
            "current_price": current_price,
            "market_value": market_value,
            "cost_basis": cost_basis,
            "unrealized_pnl": unrealized_pnl,
            "holding_return_pct": holding_return_pct
        })

    out = pd.DataFrame(rows)
    out.to_csv(HOLDINGS_PATH, index=False)
    return out

if __name__ == "__main__":
    calculate_holdings()
