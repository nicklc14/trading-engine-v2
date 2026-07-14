import pandas as pd
from pathlib import Path

DATA_DIR = Path("data")
DEPOSITS_PATH = DATA_DIR / "deposits.csv"
TRADES_PATH = DATA_DIR / "trades.csv"
CASH_PATH = DATA_DIR / "cash.csv"

def calculate_cash():
    deposits = pd.read_csv(DEPOSITS_PATH) if DEPOSITS_PATH.exists() else pd.DataFrame()
    trades = pd.read_csv(TRADES_PATH) if TRADES_PATH.exists() else pd.DataFrame()

    total_deposits_usd = deposits.get("amount_usd", pd.Series(dtype=float)).fillna(0).sum()

    buys = trades[trades["type"].astype(str).str.upper() == "BUY"] if not trades.empty else pd.DataFrame()
    sells = trades[trades["type"].astype(str).str.upper() == "SELL"] if not trades.empty else pd.DataFrame()

    buy_spend = buys.get("usd_amount", pd.Series(dtype=float)).fillna(0).sum()
    buy_fees = buys.get("transaction_fee", pd.Series(dtype=float)).fillna(0).sum()

    sell_proceeds = sells.get("usd_amount", pd.Series(dtype=float)).fillna(0).sum()
    sell_fees = sells.get("transaction_fee", pd.Series(dtype=float)).fillna(0).sum()

    cash_available_usd = total_deposits_usd - buy_spend - buy_fees + sell_proceeds - sell_fees

    out = pd.DataFrame([{
        "total_deposits_usd": total_deposits_usd,
        "buy_spend_usd": buy_spend,
        "buy_fees_usd": buy_fees,
        "sell_proceeds_usd": sell_proceeds,
        "sell_fees_usd": sell_fees,
        "cash_available_usd": cash_available_usd
    }])

    out.to_csv(CASH_PATH, index=False)
    return out

if __name__ == "__main__":
    calculate_cash()
