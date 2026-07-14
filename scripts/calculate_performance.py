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

    total_deposits = float(cash["total_deposits_usd"].iloc[0]) if not cash.empty and "total_deposits_usd" in cash.columns else 0.0
    cash_available = float(cash["cash_available_usd"].iloc[0]) if not cash.empty and "cash_available_usd" in cash.columns else 0.0

    holdings_value = float(holdings["market_value"].sum()) if not holdings.empty and "market_value" in holdings.columns else 0.0
    unrealized_pnl = float(holdings["unrealized_pnl"].sum()) if not holdings.empty and "unrealized_pnl" in holdings.columns else 0.0

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

            total_buy_shares = buys["shares"].sum()
            total_buy_cost = buys["value"].sum() + buys["transaction_fee"].fillna(0).sum()
            avg_cost = total_buy_cost / total_buy_shares if total_buy_shares > 0 else np.nan

            for _, sell in sells.iterrows():
                sell_shares = sell.get("shares", 0)
                sell_value = sell.get("value", 0)
                sell_fee = sell.get("transaction_fee", 0)
                pnl = sell_value - sell_fee - (sell_shares * avg_cost) if pd.notna(avg_cost) else 0
                realized_pnl += pnl
                sell_pnls.append(pnl)

                if pnl > 0:
                    wins += 1
                elif pnl < 0:
                    losses += 1

    portfolio_value = cash_available + holdings_value
    total_pnl = realized_pnl + unrealized_pnl
    total_return_pct = total_pnl / total_deposits if total_deposits > 0 else np.nan

    avg_win = np.mean([p for p in sell_pnls if p > 0]) if any(p > 0 for p in sell_pnls) else 0.0
    avg_loss = np.mean([p for p in sell_pnls if p < 0]) if any(p < 0 for p in sell_pnls) else 0.0
    win_rate = wins / (wins + losses) if (wins + losses) > 0 else np.nan

    out = pd.DataFrame([{
        "total_deposits_usd": round(total_deposits, 2),
        "cash_available_usd": round(cash_available, 2),
        "holdings_value_usd": round(holdings_value, 2),
        "portfolio_value_usd": round(portfolio_value, 2),
        "realized_pnl_usd": round(realized_pnl, 2),
        "unrealized_pnl_usd": round(unrealized_pnl, 2),
        "total_pnl_usd": round(total_pnl, 2),
        "total_return_pct": total_return_pct,
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
