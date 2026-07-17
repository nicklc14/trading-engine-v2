import pandas as pd
from pathlib import Path

DATA_DIR = Path("data")
TRADES_PATH = DATA_DIR / "trades.csv"

COLUMNS = [
    "date", "ticker", "type", "price", "usd_amount", "transaction_fee",
    "shares", "value", "holding_key", "sell_method", "notes"
]

def is_blank(x):
    return pd.isna(x) or str(x).strip() == ""

def next_key(existing_keys):
    nums = pd.to_numeric(existing_keys, errors="coerce").dropna()
    return int(nums.max()) + 1 if len(nums) else 1

def normalize_trades():
    trades = pd.read_csv(
        TRADES_PATH,
        dtype={"shares": "string", "holding_key": "string", "sell_method": "string"}
    )

    for col in COLUMNS:
        if col not in trades.columns:
            trades[col] = ""

    trades = trades[COLUMNS]

    trades["ticker"] = trades["ticker"].astype(str).str.upper().str.strip()
    trades["type"] = trades["type"].astype(str).str.title().str.strip()
    trades["holding_key"] = trades["holding_key"].astype("string").str.strip()
    trades["sell_method"] = trades["sell_method"].astype("string").str.upper().str.strip()

    for col in ["price", "usd_amount", "transaction_fee", "value"]:
        trades[col] = pd.to_numeric(trades[col], errors="coerce")

    shares_raw = trades["shares"].astype("string").str.strip()
    shares_is_all = shares_raw.str.upper().eq("ALL")
    trades["shares"] = pd.to_numeric(shares_raw.mask(shares_is_all), errors="coerce")

    # Auto-assign holding keys to buy rows.
    assigned_keys = []
    existing_keys = trades["holding_key"].copy()

    for i, row in trades.iterrows():
        if row["type"] == "Buy":
            if is_blank(row["holding_key"]):
                new_key = next_key(pd.Series(list(existing_keys.dropna()) + assigned_keys))
                trades.at[i, "holding_key"] = str(new_key)
                assigned_keys.append(str(new_key))

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

    output_rows = []

    for i, row in trades.iterrows():
        if row["type"] != "Sell":
            output_rows.append(row.to_dict())
            continue

        ticker = row["ticker"]
        method = row["sell_method"] if not is_blank(row["sell_method"]) else "FIFO"

        # Calculate sell shares if blank.
        sell_shares = row["shares"]

        if shares_is_all.iloc[i]:
            sell_shares = None
        elif pd.isna(sell_shares):
            if pd.notna(row["value"]) and row["price"] > 0:
                sell_shares = row["value"] / row["price"]
            elif pd.notna(row["usd_amount"]) and row["price"] > 0:
                # Sell usd_amount is treated as net proceeds after fee.
                gross_value = row["usd_amount"] + (row["transaction_fee"] if pd.notna(row["transaction_fee"]) else 0)
                sell_shares = gross_value / row["price"]

        if method not in ["FIFO", "SPECIFIC"]:
            raise ValueError(f"Unsupported sell_method '{method}' on CSV line {i + 2}")

        # SPECIFIC behaves like old holding_key logic.
        if method == "SPECIFIC" or not is_blank(row["holding_key"]):
            if is_blank(row["holding_key"]):
                raise ValueError(f"SPECIFIC sell requires holding_key on CSV line {i + 2}")

            if sell_shares is None:
                key = str(row["holding_key"])
                prior = pd.DataFrame(output_rows)

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

                sell_shares = max(buys - sells, 0)

            row["shares"] = sell_shares
            row["value"] = row["price"] * sell_shares if pd.notna(row["price"]) else row["value"]
            output_rows.append(row.to_dict())
            continue

        # FIFO sell.
        prior = pd.DataFrame(output_rows)

        buys = prior[
            (prior["type"] == "Buy")
            & (prior["ticker"] == ticker)
        ].copy()

        if buys.empty:
            raise ValueError(f"No open buy lots found for FIFO sell of {ticker} on CSV line {i + 2}")

        lots = []

        for _, buy in buys.iterrows():
            key = str(buy["holding_key"])
            bought = float(buy["shares"])

            sold = prior[
                (prior["type"] == "Sell")
                & (prior["ticker"] == ticker)
                & (prior["holding_key"].astype(str) == key)
            ]["shares"].sum()

            remaining = bought - sold
            if remaining > 1e-10:
                lots.append({"key": key, "remaining": remaining})

        total_open = sum(l["remaining"] for l in lots)

        if sell_shares is None:
            sell_shares = total_open

        if pd.isna(sell_shares) or sell_shares <= 0:
            raise ValueError(f"Sell row must have shares, ALL, value, or usd_amount on CSV line {i + 2}")

        if sell_shares > total_open + 1e-8:
            raise ValueError(
                f"Sell quantity for {ticker} exceeds open shares on CSV line {i + 2}. "
                f"Trying to sell {sell_shares:.9f}, open {total_open:.9f}"
            )

        remaining_to_sell = float(sell_shares)

        for lot in lots:
            if remaining_to_sell <= 1e-10:
                break

            split_shares = min(lot["remaining"], remaining_to_sell)
            split = row.copy()

            split["shares"] = split_shares
            split["holding_key"] = lot["key"]
            split["sell_method"] = "FIFO"
            split["value"] = split["price"] * split_shares if pd.notna(split["price"]) else split["value"]

            # Allocate fee and net proceeds proportionally.
            fraction = split_shares / sell_shares

            if pd.notna(row["transaction_fee"]):
                split["transaction_fee"] = row["transaction_fee"] * fraction

            if pd.notna(row["usd_amount"]):
                split["usd_amount"] = row["usd_amount"] * fraction

            note = "" if is_blank(split["notes"]) else str(split["notes"])
            split["notes"] = f"{note} | Auto FIFO split".strip(" |")

            output_rows.append(split.to_dict())
            remaining_to_sell -= split_shares

    out = pd.DataFrame(output_rows)

    for col in ["price", "usd_amount", "transaction_fee", "shares", "value"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")

    # Recalculate value where possible.
    can_calc_value = out["price"].notna() & out["shares"].notna()
    out.loc[can_calc_value, "value"] = out.loc[can_calc_value, "price"] * out.loc[can_calc_value, "shares"]

    # If usd_amount missing, infer cash movement.
    missing_usd = out["usd_amount"].isna()
    fees = out["transaction_fee"].fillna(0)

    buy_missing_usd = missing_usd & (out["type"] == "Buy")
    out.loc[buy_missing_usd, "usd_amount"] = out.loc[buy_missing_usd, "value"] + fees[buy_missing_usd]

    sell_missing_usd = missing_usd & (out["type"] == "Sell")
    out.loc[sell_missing_usd, "usd_amount"] = out.loc[sell_missing_usd, "value"] - fees[sell_missing_usd]

    out = out[COLUMNS]
    out.to_csv(TRADES_PATH, index=False)
    return out

if __name__ == "__main__":
    normalize_trades()
