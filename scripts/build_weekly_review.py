import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path("data")
TRADES_PATH = DATA_DIR / "trades.csv"
WEEKLY_REVIEW_PATH = DATA_DIR / "weekly_review.csv"

def build_weekly_review():
    if not TRADES_PATH.exists():
        pd.DataFrame().to_csv(WEEKLY_REVIEW_PATH, index=False)
        return pd.DataFrame()

    trades = pd.read_csv(TRADES_PATH)
    trades["date"] = pd.to_datetime(trades["date"], errors="coerce")
    trades["type"] = trades["type"].astype(str).str.title().str.strip()
    trades["ticker"] = trades["ticker"].astype(str).str.upper().str.strip()

    for col in ["usd_amount", "transaction_fee", "shares", "value"]:
        trades[col] = pd.to_numeric(trades.get(col, 0), errors="coerce").fillna(0)

    sells = trades[trades["type"] == "Sell"].copy()

    rows = []
    for _, sell in sells.iterrows():
        key = sell.get("holding_key", "")
        ticker = sell["ticker"]

        buys = trades[
            (trades["type"] == "Buy")
            & (trades["ticker"] == ticker)
            & (trades["holding_key"].astype(str) == str(key))
        ]

        buy_cost = buys["usd_amount"].sum()
        sell_proceeds = sell["usd_amount"]

        pnl = sell_proceeds - buy_cost
        return_pct = pnl / buy_cost if buy_cost else np.nan

        rows.append({
            "week_start": sell["date"].to_period("W").start_time.date() if pd.notna(sell["date"]) else "",
            "sell_date": sell["date"].date() if pd.notna(sell["date"]) else "",
            "ticker": ticker,
            "holding_key": key,
            "buy_cost_usd": buy_cost,
            "sell_proceeds_usd": sell_proceeds,
            "realized_pnl_usd": pnl,
            "realized_return_pct": return_pct,
            "result": "WIN" if pnl > 0 else "LOSS" if pnl < 0 else "FLAT",
            "notes": sell.get("notes", ""),
        })

    closed = pd.DataFrame(rows)

    if closed.empty:
        out = pd.DataFrame([{
            "week_start": "",
            "closed_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0,
            "realized_pnl_usd": 0,
            "avg_return_pct": 0,
            "best_trade": "",
            "worst_trade": "",
        }])
    else:
        grouped = []
        for week, g in closed.groupby("week_start"):
            wins = (g["realized_pnl_usd"] > 0).sum()
            losses = (g["realized_pnl_usd"] < 0).sum()
            closed_count = len(g)

            best = g.sort_values("realized_pnl_usd", ascending=False).iloc[0]
            worst = g.sort_values("realized_pnl_usd", ascending=True).iloc[0]

            grouped.append({
                "week_start": week,
                "closed_trades": closed_count,
                "wins": wins,
                "losses": losses,
                "win_rate": wins / closed_count if closed_count else 0,
                "realized_pnl_usd": g["realized_pnl_usd"].sum(),
                "avg_return_pct": g["realized_return_pct"].mean(),
                "best_trade": f"{best['ticker']} {best['realized_pnl_usd']:.2f}",
                "worst_trade": f"{worst['ticker']} {worst['realized_pnl_usd']:.2f}",
            })

        out = pd.DataFrame(grouped)

    out.to_csv(WEEKLY_REVIEW_PATH, index=False)
    return out

if __name__ == "__main__":
    build_weekly_review()
