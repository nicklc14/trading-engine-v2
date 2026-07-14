import pandas as pd
from pathlib import Path

DATA_DIR = Path("data")
TRADES_PATH = DATA_DIR / "trades.csv"

COLUMNS = [
    "date","ticker","type","price","usd_amount","transaction_fee",
    "shares","value","holding_key","notes"
]

def normalize_trades():
    trades = pd.read_csv(TRADES_PATH)

    for col in COLUMNS:
        if col not in trades.columns:
            trades[col] = ""

    trades = trades[COLUMNS]

    trades["ticker"] = trades["ticker"].astype(str).str.upper().str.strip()
    trades["type"] = trades["type"].astype(str).str.title().str.strip()
    trades["holding_key"] = trades["holding_key"].astype("string")

    for col in ["price","usd_amount","transaction_fee","shares","value"]:
        trades[col] = pd.to_numeric(trades[col], errors="coerce")

    missing_shares = trades["shares"].isna() & trades["price"].gt(0) & trades["usd_amount"].notna()
    trades.loc[missing_shares, "shares"] = (
        (trades.loc[missing_shares, "usd_amount"] - trades.loc[missing_shares, "transaction_fee"].fillna(0))
        / trades.loc[missing_shares, "price"]
    )

    trades["value"] = trades["price"] * trades["shares"]

    missing_usd = trades["usd_amount"].isna()
    fees = trades["transaction_fee"].fillna(0)

    trades.loc[missing_usd & (trades["type"] == "Buy"), "usd_amount"] = trades["value"] + fees
    trades.loc[missing_usd & (trades["type"] == "Sell"), "usd_amount"] = trades["value"] - fees

    blank_key = trades["holding_key"].isna() | (trades["holding_key"].str.strip() == "")

    if blank_key.any():
        trades.loc[blank_key, "holding_key"] = (
            trades.loc[blank_key, "ticker"].astype(str)
            + "-"
            + trades.loc[blank_key, "date"].astype(str).str.replace("-", "", regex=False)
        )

    trades.to_csv(TRADES_PATH, index=False)
    return trades

if __name__ == "__main__":
    normalize_trades()
