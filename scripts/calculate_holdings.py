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

        buy_shares = g[g["type"].astype(str).str.upper() == "BUY"]["shares"].sum()
        sell_shares = g[g["type"].astype(str).str.upper() == "SELL"]["shares"].sum()
        shares = buy_shares - sell_shares

        if shares <= 0:
            continue

        current_price = price_map.get(ticker, np.nan)
        market_value = shares * current_price if pd.notna(current_price) else np.nan

        rows.append({
            "ticker": ticker,
            "shares": shares,
            "current_price": current_price,
            "market_value": market_value
        })

    out = pd.DataFrame(rows)
    out.to_csv(HOLDINGS_PATH, index=False)
    return out

if __name__ == "__main__":
    calculate_holdings()
