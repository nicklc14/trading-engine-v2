import pandas as pd
from pathlib import Path

DATA_DIR = Path("data")
DEPOSITS_PATH = DATA_DIR / "deposits.csv"
TRADES_PATH = DATA_DIR / "trades.csv"
CASH_PATH = DATA_DIR / "cash.csv"

def calculate_cash():
    deposits = pd.read_csv(DEPOSITS_PATH) if DEPOSITS_PATH.exists() else pd.DataFrame()
    trades = pd.read_csv(TRADES_PATH) if TRADES_PATH.exists() else pd.DataFrame()

    total_deposits_usd = pd.to_numeric(
        deposits.get("amount_usd", pd.Series(dtype=float)),
        errors="coerce"
    ).fillna(0).sum()

    if len(trades):
        trades["type"] = trades["type"].astype(str).str.title().str.strip()
        trades["usd_amount"] = pd.to_numeric(trades.get("usd_amount", 0), errors="coerce").fillna(0)
        trades["transaction_fee"] = pd.to_numeric(trades.get("transaction_fee", 0), errors="coerce").fillna(0)

        buy_spend_usd = trades.loc[trades["type"] == "Buy", "usd_amount"].sum()
        sell_proceeds_usd = trades.loc[trades["type"] == "Sell", "usd_amount"].sum()

        # Fees are already included in usd_amount.
        buy_fees_usd = trades.loc[trades["type"] == "Buy", "transaction_fee"].sum()
        sell_fees_usd = trades.loc[trades["type"] == "Sell", "transaction_fee"].sum()
    else:
        buy_spend_usd = 0
        sell_proceeds_usd = 0
        buy_fees_usd = 0
        sell_fees_usd = 0

    cash_available_usd = total_deposits_usd - buy_spend_usd + sell_proceeds_usd

    out = pd.DataFrame([{
        "total_deposits_usd": total_deposits_usd,
        "buy_spend_usd": buy_spend_usd,
        "buy_fees_usd": buy_fees_usd,
        "sell_proceeds_usd": sell_proceeds_usd,
        "sell_fees_usd": sell_fees_usd,
        "cash_available_usd": cash_available_usd,
    }])

    out.to_csv(CASH_PATH, index=False)
    return out
    
if __name__ == "__main__":
    calculate_cash()
