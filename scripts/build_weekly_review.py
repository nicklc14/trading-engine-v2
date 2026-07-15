import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path("data")

TRADES_PATH = DATA_DIR / "trades.csv"
SIGNALS_PATH = DATA_DIR / "signals.csv"
WATCHLIST_PATH = DATA_DIR / "watchlist.csv"
WEEKLY_REVIEW_PATH = DATA_DIR / "weekly_review.csv"
PERFORMANCE_LEARNING_PATH = DATA_DIR / "performance_learning.csv"
CLOSED_TRADES_PATH = DATA_DIR / "closed_trades_learning.csv"

def read_csv_safe(path):
    if path.exists() and path.stat().st_size > 0:
        return pd.read_csv(path)
    return pd.DataFrame()

def build_weekly_review():
    trades = read_csv_safe(TRADES_PATH)
    signals = read_csv_safe(SIGNALS_PATH)
    watchlist = read_csv_safe(WATCHLIST_PATH)

    if trades.empty:
        weekly = pd.DataFrame([{
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
        learning = pd.DataFrame([{
            "group_type": "status",
            "group_value": "Not enough closed trades yet",
            "closed_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0,
            "realized_pnl_usd": 0,
            "avg_return_pct": 0,
            "avg_pnl_usd": 0,
        }])
        weekly.to_csv(WEEKLY_REVIEW_PATH, index=False)
        learning.to_csv(PERFORMANCE_LEARNING_PATH, index=False)
        pd.DataFrame().to_csv(CLOSED_TRADES_PATH, index=False)
        return weekly

    trades["date"] = pd.to_datetime(trades["date"], errors="coerce")
    trades["ticker"] = trades["ticker"].astype(str).str.upper().str.strip()
    trades["type"] = trades["type"].astype(str).str.title().str.strip()
    trades["holding_key"] = trades["holding_key"].astype(str).str.strip()

    for col in ["usd_amount", "shares", "value", "transaction_fee", "price"]:
        trades[col] = pd.to_numeric(trades.get(col, 0), errors="coerce").fillna(0)

    tier_map = {}
    if not watchlist.empty:
        watchlist["ticker"] = watchlist["ticker"].astype(str).str.upper().str.strip()
        tier_map = dict(zip(watchlist["ticker"], watchlist.get("tier", "")))

    signal_map = {}
    if not signals.empty:
        signals["ticker"] = signals["ticker"].astype(str).str.upper().str.strip()
        for _, r in signals.iterrows():
            signal_map[r["ticker"]] = {
                "latest_score": r.get("score", np.nan),
                "latest_action": r.get("action", ""),
                "latest_reasons": r.get("decision_reasons", ""),
                "latest_warnings": r.get("warnings", ""),
                "market_regime": r.get("market_regime", ""),
                "aggressive_mode_active": r.get("aggressive_mode_active", ""),
                "add_more_signal": r.get("add_more_signal", ""),
                "exit_action": r.get("exit_action", ""),
                "exit_reason": r.get("exit_reason", ""),
            }

    closed_rows = []
    sells = trades[trades["type"] == "Sell"].copy()

    for _, sell in sells.iterrows():
        ticker = sell["ticker"]
        key = str(sell["holding_key"])

        buys = trades[
            (trades["type"] == "Buy")
            & (trades["ticker"] == ticker)
            & (trades["holding_key"].astype(str) == key)
        ].copy()

        if buys.empty:
            continue

        first_buy_date = buys["date"].min()
        sell_date = sell["date"]
        holding_days = (sell_date - first_buy_date).days if pd.notna(sell_date) and pd.notna(first_buy_date) else np.nan

        buy_cost = buys["usd_amount"].sum()
        buy_fees = buys["transaction_fee"].sum()
        total_buy_cost = buy_cost

        sell_proceeds = sell["usd_amount"]
        sell_fee = sell["transaction_fee"]

        pnl = sell_proceeds - total_buy_cost
        return_pct = pnl / total_buy_cost if total_buy_cost else np.nan

        week_start = sell_date.to_period("W").start_time.date() if pd.notna(sell_date) else ""
        signal_info = signal_map.get(ticker, {})

        result = "WIN" if pnl > 0 else "LOSS" if pnl < 0 else "FLAT"

        closed_rows.append({
            "week_start": week_start,
            "sell_date": sell_date.date() if pd.notna(sell_date) else "",
            "ticker": ticker,
            "tier": tier_map.get(ticker, ""),
            "holding_key": key,
            "first_buy_date": first_buy_date.date() if pd.notna(first_buy_date) else "",
            "holding_days": holding_days,
            "buy_cost_usd": round(buy_cost, 2),
            "buy_fees_usd": round(buy_fees, 2),
            "sell_proceeds_usd": round(sell_proceeds, 2),
            "sell_fee_usd": round(sell_fee, 2),
            "realized_pnl_usd": round(pnl, 2),
            "realized_return_pct": return_pct,
            "result": result,
            "latest_score": signal_info.get("latest_score", np.nan),
            "latest_action": signal_info.get("latest_action", ""),
            "latest_reasons": signal_info.get("latest_reasons", ""),
            "latest_warnings": signal_info.get("latest_warnings", ""),
            "market_regime": signal_info.get("market_regime", ""),
            "aggressive_mode_active": signal_info.get("aggressive_mode_active", ""),
            "add_more_signal": signal_info.get("add_more_signal", ""),
            "exit_action": signal_info.get("exit_action", ""),
            "exit_reason": signal_info.get("exit_reason", ""),
            "notes": sell.get("notes", ""),
        })

    closed = pd.DataFrame(closed_rows)
    closed.to_csv(CLOSED_TRADES_PATH, index=False)

    if closed.empty:
        weekly = pd.DataFrame([{
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
        weekly_rows = []
        for week, g in closed.groupby("week_start"):
            wins = (g["realized_pnl_usd"] > 0).sum()
            losses = (g["realized_pnl_usd"] < 0).sum()
            count = len(g)

            best = g.sort_values("realized_pnl_usd", ascending=False).iloc[0]
            worst = g.sort_values("realized_pnl_usd", ascending=True).iloc[0]

            weekly_rows.append({
                "week_start": week,
                "closed_trades": count,
                "wins": wins,
                "losses": losses,
                "win_rate": wins / count if count else 0,
                "realized_pnl_usd": g["realized_pnl_usd"].sum(),
                "avg_return_pct": g["realized_return_pct"].mean(),
                "avg_holding_days": g["holding_days"].mean(),
                "best_trade": f"{best['ticker']} {best['realized_pnl_usd']:.2f}",
                "worst_trade": f"{worst['ticker']} {worst['realized_pnl_usd']:.2f}",
            })

        weekly = pd.DataFrame(weekly_rows)

    learning_rows = []

    if not closed.empty:
        group_fields = [
            "tier",
            "latest_action",
            "latest_reasons",
            "market_regime",
            "aggressive_mode_active",
            "exit_action",
            "exit_reason",
        ]

        for field in group_fields:
            if field not in closed.columns:
                continue

            for value, g in closed.groupby(field, dropna=False):
                count = len(g)
                wins = (g["realized_pnl_usd"] > 0).sum()
                losses = (g["realized_pnl_usd"] < 0).sum()

                learning_rows.append({
                    "group_type": field,
                    "group_value": value,
                    "closed_trades": count,
                    "wins": wins,
                    "losses": losses,
                    "win_rate": wins / count if count else 0,
                    "realized_pnl_usd": g["realized_pnl_usd"].sum(),
                    "avg_return_pct": g["realized_return_pct"].mean(),
                    "avg_pnl_usd": g["realized_pnl_usd"].mean(),
                    "avg_holding_days": g["holding_days"].mean(),
                })

    if not learning_rows:
        learning = pd.DataFrame([{
            "group_type": "status",
            "group_value": "Not enough closed trades yet",
            "closed_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0,
            "realized_pnl_usd": 0,
            "avg_return_pct": 0,
            "avg_pnl_usd": 0,
            "avg_holding_days": 0,
        }])
    else:
        learning = pd.DataFrame(learning_rows)

    weekly.to_csv(WEEKLY_REVIEW_PATH, index=False)
    learning.to_csv(PERFORMANCE_LEARNING_PATH, index=False)

    return weekly

if __name__ == "__main__":
    build_weekly_review()
