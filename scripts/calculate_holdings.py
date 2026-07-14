import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path("data")
TRADES_PATH = DATA_DIR / "trades.csv"
MARKET_PATH = DATA_DIR / "market_data.csv"
HOLDINGS_PATH = DATA_DIR / "holdings.csv"

def calculate_holdings():
    if not TRADES_PATH.exists():
        pd.DataFrame(columns=[
            "ticker","shares","avg_cost","cost_basis","current_price",
            "market_value","unrealized_pnl","holding_return_pct"
        ]).to_csv(HOLDINGS_PATH, index=False)
        return pd.DataFrame()

    trades = pd.read_csv(TRADES_PATH)
    market = pd.read_csv(MARKET_PATH) if MARKET_PATH.exists() else pd.DataFrame()

    for col in ["price","usd_amount","transaction_fee","shares","value"]:
        trades[col] = pd.to_numeric(trades.get(col, 0), errors="coerce").fillna(0)

    trades["ticker"] = trades["ticker"].astype(str).str.upper().str.strip()
    trades["type"] = trades["type"].astype(str).str.title().str.strip()

    price_map = dict(zip(
        market.get("ticker", pd.Series(dtype=str)).astype(str).str.upper().str.strip(),
        pd.to_numeric(market.get("price", pd.Series(dtype=float)), errors="coerce")
    ))

    rows = []

    for ticker, g in trades.groupby("ticker"):
        if ticker in ["CASH", "DEPOSIT", ""]:
            continue

        buys = g[g["type"] == "Buy"]
        sells = g[g["type"] == "Sell"]

        buy_shares = buys["shares"].sum()
        sell_shares = sells["shares"].sum()
        shares = buy_shares - sell_shares

        if shares <= 0:
            continue

        total_buy_cost = (buys["price"] * buys["shares"]).sum() + buys["transaction_fee"].sum()
        avg_cost = total_buy_cost / buy_shares if buy_shares else 0
        cost_basis = avg_cost * shares

        current_price = price_map.get(ticker, np.nan)
        market_value = shares * current_price if pd.notna(current_price) else np.nan

        unrealized_pnl = market_value - cost_basis if pd.notna(market_value) else np.nan
        holding_return_pct = unrealized_pnl / cost_basis if cost_basis else np.nan

        rows.append({
            "ticker": ticker,
            "shares": shares,
            "avg_cost": avg_cost,
            "cost_basis": cost_basis,
            "current_price": current_price,
            "market_value": market_value,
            "unrealized_pnl": unrealized_pnl,
            "holding_return_pct": holding_return_pct,
        })

    out = pd.DataFrame(rows)
    out.to_csv(HOLDINGS_PATH, index=False)
    return out

if __name__ == "__main__":
    calculate_holdings()
