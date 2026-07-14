import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path("data")
TRADES_PATH = DATA_DIR / "trades.csv"
HOLDINGS_PATH = DATA_DIR / "holdings.csv"
CASH_PATH = DATA_DIR / "cash.csv"
PERFORMANCE_PATH = DATA_DIR / "performance.csv"

def calculate_performance():
    trades = pd.read_csv(TRADES_PATH) if TRADES_PATH.exists() else pd.DataFrame()
    holdings = pd.read_csv(HOLDINGS_PATH) if HOLDINGS_PATH.exists() else pd.DataFrame()
    cash = pd.read_csv(CASH_PATH) if CASH_PATH.exists() else pd.DataFrame()

    total_deposits = float(cash["total_deposits_usd"].iloc[0]) if not cash.empty else 0.0
    cash_available = float(cash["cash_available_usd"].iloc[0]) if not cash.empty else 0.0

    holdings_value = float(holdings["market_value"].sum()) if "market_value" in holdings.columns else 0.0
    unrealized_pnl = float(holdings["unrealized_pnl"].sum()) if "unrealized_pnl" in holdings.columns else 0.0

    account_equity_usd = cash_available + holdings_value
    account_pnl_usd = account_equity_usd - total_deposits
    account_return_pct = account_pnl_usd / total_deposits if total_deposits > 0 else np.nan

    realized_pnl = 0.0
    wins = 0
    losses = 0
    sell_pnls = []

    if not trades.empty:
        trades["type_upper"] = trades["type"].astype(str).str.upper()

        for ticker, g in trades.groupby("ticker"):
            ticker = str(ticker).upper()
            if ticker in ["CASH", "DEPOSIT"]:
                continue

            buys = g[g["type_upper"] == "BUY"]
            sells = g[g["type_upper"] == "SELL"]

            buy_shares = buys["shares"].sum()
            buy_cost = buys["value"].sum() + buys["transaction_fee"].fillna(0).sum()
            avg_cost = buy_cost / buy_shares if buy_shares > 0 else np.nan

            for _, sell in sells.iterrows():
                if pd.isna(avg_cost):
                    continue
                pnl = sell["value"] - sell["transaction_fee"] - (sell["shares"] * avg_cost)
                realized_pnl += pnl
                sell_pnls.append(pnl)
                if pnl > 0:
                    wins += 1
                elif pnl < 0:
                    losses += 1

    win_rate = wins / (wins + losses) if wins + losses > 0 else np.nan
    avg_win = np.mean([p for p in sell_pnls if p > 0]) if any(p > 0 for p in sell_pnls) else 0.0
    avg_loss = np.mean([p for p in sell_pnls if p < 0]) if any(p < 0 for p in sell_pnls) else 0.0

    out = pd.DataFrame([{
        "total_deposits_usd": round(total_deposits, 2),
        "cash_available_usd": round(cash_available, 2),
        "holdings_value_usd": round(holdings_value, 2),
        "account_equity_usd": round(account_equity_usd, 2),
        "account_pnl_usd": round(account_pnl_usd, 2),
        "account_return_pct": account_return_pct,
        "realized_pnl_usd": round(realized_pnl, 2),
        "unrealized_pnl_usd": round(unrealized_pnl, 2),
        "closed_wins": wins,
        "closed_losses": losses,
        "win_rate": win_rate,
        "avg_win_usd": round(avg_win, 2),
        "avg_loss_usd": round(avg_loss, 2)
    }])

    out.to_csv(PERFORMANCE_PATH, index=False)
    return out

if __name__ == "__main__":
    calculate_performance()
