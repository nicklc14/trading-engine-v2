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

    total_deposits_usd = deposits.get("amount_usd", pd.Series(dtype=float)).fillna(0).sum()

    if trades.empty:
        buy_spend_usd = buy_fees_usd = sell_proceeds_usd = sell_fees_usd = 0
    else:
        trades["type"] = trades["type"].astype(str).str.upper()
        trades["usd_amount"] = pd.to_numeric(trades["usd_amount"], errors="coerce").fillna(0)
        trades["transaction_fee"] = pd.to_numeric(trades["transaction_fee"], errors="coerce").fillna(0)

        buy_rows = trades[trades["type"] == "BUY"]
        sell_rows = trades[trades["type"] == "SELL"]

        buy_spend_usd = buy_rows["usd_amount"].sum()
        buy_fees_usd = buy_rows["transaction_fee"].sum()
        sell_proceeds_usd = sell_rows["usd_amount"].sum()
        sell_fees_usd = sell_rows["transaction_fee"].sum()

    cash_available_usd = (
        total_deposits_usd
        - buy_spend_usd
        - buy_fees_usd
        + sell_proceeds_usd
        - sell_fees_usd
    )

    cash = pd.DataFrame([{
        "total_deposits_usd": total_deposits_usd,
        "buy_spend_usd": buy_spend_usd,
        "buy_fees_usd": buy_fees_usd,
        "sell_proceeds_usd": sell_proceeds_usd,
        "sell_fees_usd": sell_fees_usd,
        "cash_available_usd": cash_available_usd,
    }])

    cash.to_csv(CASH_PATH, index=False)
    return cash


if __name__ == "__main__":
    calculate_cash()
