import pandas as pd
from pathlib import Path

DATA_DIR = Path("data")

TRADES_PATH = DATA_DIR / "trades.csv"
DEPOSITS_PATH = DATA_DIR / "deposits.csv"
CASH_PATH = DATA_DIR / "cash.csv"


def read_csv_safe(path):
    if path.exists() and path.stat().st_size > 0:
        return pd.read_csv(path)
    return pd.DataFrame()


def calculate_cash():
    trades = read_csv_safe(TRADES_PATH)
    deposits = read_csv_safe(DEPOSITS_PATH)

    if deposits.empty or "amount_usd" not in deposits.columns:
        total_deposits_usd = 0.0
    else:
        deposits["amount_usd"] = pd.to_numeric(deposits["amount_usd"], errors="coerce").fillna(0)
        total_deposits_usd = deposits["amount_usd"].sum()

    if trades.empty:
        buy_spend_usd = 0.0
        buy_fees_usd = 0.0
        sell_proceeds_usd = 0.0
        sell_fees_usd = 0.0
    else:
        trades["type"] = trades["type"].astype(str).str.upper()
        trades["usd_amount"] = pd.to_numeric(trades["usd_amount"], errors="coerce").fillna(0)
        trades["transaction_fee"] = pd.to_numeric(trades["transaction_fee"], errors="coerce").fillna(0)

        buys = trades[trades["type"] == "BUY"]
        sells = trades[trades["type"] == "SELL"]

        buy_spend_usd = buys["usd_amount"].sum()
        buy_fees_usd = buys["transaction_fee"].sum()
        sell_proceeds_usd = sells["usd_amount"].sum()
        sell_fees_usd = sells["transaction_fee"].sum()

    cash_available_usd = (
        total_deposits_usd
        - buy_spend_usd
        - buy_fees_usd
        + sell_proceeds_usd
        - sell_fees_usd
    )

    cash = pd.DataFrame([{
        "total_deposits_usd": round(total_deposits_usd, 5),
        "buy_spend_usd": round(buy_spend_usd, 5),
        "buy_fees_usd": round(buy_fees_usd, 5),
        "sell_proceeds_usd": round(sell_proceeds_usd, 5),
        "sell_fees_usd": round(sell_fees_usd, 5),
        "cash_available_usd": round(cash_available_usd, 5),
    }])

    cash.to_csv(CASH_PATH, index=False)
    return cash


if __name__ == "__main__":
    calculate_cash()
