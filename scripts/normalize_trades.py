import pandas as pd
from pathlib import Path

DATA_DIR = Path("data")
TRADES_PATH = DATA_DIR / "trades.csv"

COLUMNS = [
    "date","ticker","type","price","usd_amount","transaction_fee",
    "shares","value","holding_key","notes"
]

def normalize_trades():
    trades = pd.read_csv(TRADES_PATH, dtype={"shares": "string", "holding_key": "string"})

    for col in COLUMNS:
        if col not in trades.columns:
            trades[col] = ""

    trades = trades[COLUMNS]

    trades["ticker"] = trades["ticker"].astype(str).str.upper().str.strip()
    trades["type"] = trades["type"].astype(str).str.title().str.strip()
    trades["holding_key"] = trades["holding_key"].astype("string").str.strip()

    for col in ["price", "usd_amount", "transaction_fee", "value"]:
        trades[col] = pd.to_numeric(trades[col], errors="coerce")

    shares_raw = trades["shares"].astype("string").str.strip()
    shares_is_all = shares_raw.str.upper().eq("ALL")
    trades["shares"] = pd.to_numeric(shares_raw.mask(shares_is_all), errors="coerce")

    # BUY: auto-calculate shares if blank.
    buy_missing_shares = (
        (trades["type"] == "Buy")
        & trades["shares"].isna()
        & trades["price"].gt(0)
        & trades["usd_amount"].notna()
    )
    trades.loc[buy_missing_shares, "shares"] = (
        (trades.loc[buy_missing_shares, "usd_amount"]
         - trades.loc[buy_missing_shares, "transaction_fee"].fillna(0))
        / trades.loc[buy_missing_shares, "price"]
    )

    # SELL with shares = ALL: fill remaining open shares for that ticker/key.
    for i, row in trades[shares_is_all & (trades["type"] == "Sell")].iterrows():
        ticker = row["ticker"]
        key = str(row["holding_key"])

        prior = trades.loc[:i-1]
        buys = prior[
            (prior["type"] == "Buy")
            & (prior["ticker"] == ticker)
            & (prior["holding_key"].astype(str) == key)
        ]["shares"].sum()

        sells = prior[
            (prior["type"] == "Sell")
            & (prior["ticker"] == ticker)
            & (prior["holding_key"].astype(str) == key)
        ]["shares"].sum()

        remaining = buys - sells
        trades.at[i, "shares"] = max(remaining, 0)

    # SELL: require shares if not ALL.
    bad_sells = (trades["type"] == "Sell") & trades["shares"].isna()
    if bad_sells.any():
        bad_rows = (trades.index[bad_sells] + 2).tolist()
        raise ValueError(f"Sell rows must have shares or ALL. Problem CSV line(s): {bad_rows}")

    # Calculate value from price * shares.
    trades["value"] = trades["price"] * trades["shares"]

    # If usd_amount missing, infer cash movement.
    missing_usd = trades["usd_amount"].isna()
    fees = trades["transaction_fee"].fillna(0)

    trades.loc[missing_usd & (trades["type"] == "Buy"), "usd_amount"] = trades["value"] + fees
    trades.loc[missing_usd & (trades["type"] == "Sell"), "usd_amount"] = trades["value"] - fees

    # Auto holding key if blank.
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
