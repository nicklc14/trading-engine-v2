import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path("data")
SIGNALS_PATH = DATA_DIR / "signals.csv"
MARKET_PATH = DATA_DIR / "market_data.csv"
WATCHLIST_PATH = DATA_DIR / "watchlist.csv"
CASH_PATH = DATA_DIR / "cash.csv"
HOLDINGS_PATH = DATA_DIR / "holdings.csv"
CONFIG_PATH = DATA_DIR / "config.csv"
WEEKLY_REVIEW_PATH = DATA_DIR / "weekly_review.csv"

def clamp(x, lo=0, hi=100):
    return max(lo, min(hi, x))

def load_config():
    defaults = {
        "max_positions": 6,
        "cash_reserve_pct": 0,
        "risk_pct_per_trade": 0.05,
        "max_position_pct": 0.35,
        "block_new_buys_on_high_sell": "TRUE",
        "weekly_loss_stop_pct": 0.10,
        "momentum_priority_boost": 5,
        "quality_position_size_factor": 0.65,
        "add_more_min_return": 0.05,
        "add_more_min_score": 80,
    }

    if CONFIG_PATH.exists():
        cfg = pd.read_csv(CONFIG_PATH)
        for _, r in cfg.iterrows():
            defaults[str(r["setting"])] = r["value"]

    return defaults

def cfg_float(cfg, key):
    return float(cfg.get(key, 0))

def cfg_int(cfg, key):
    return int(float(cfg.get(key, 0)))

def cfg_bool(cfg, key):
    return str(cfg.get(key, "")).strip().upper() in ["TRUE", "YES", "1", "Y"]

def review_priority(action, exit_action="", exit_priority="", position_rule=""):
    action = str(action).upper()
    exit_action = str(exit_action).upper()
    exit_priority = str(exit_priority).upper()
    position_rule = str(position_rule).upper()

    if exit_action == "SELL" and exit_priority == "HIGH":
        return 1
    if exit_action == "SELL":
        return 2
    if "ALREADY HELD" in position_rule:
        return 3
    if action == "BUY":
        return 5
    if action == "BUY SMALL":
        return 6
    if action == "WATCH":
        return 7
    return 8

def get_cash_available():
    if not CASH_PATH.exists():
        return 0.0
    try:
        cash = pd.read_csv(CASH_PATH)
        if "cash_available_usd" in cash.columns and not cash.empty:
            return float(cash["cash_available_usd"].iloc[0])
    except Exception:
        pass
    return 0.0

def weekly_loss_stop_triggered(equity, weekly_loss_stop_pct):
    if not WEEKLY_REVIEW_PATH.exists() or equity <= 0:
        return False

    try:
        weekly = pd.read_csv(WEEKLY_REVIEW_PATH)
        if weekly.empty or "realized_pnl_usd" not in weekly.columns:
            return False

        latest = weekly.tail(1).iloc[0]
        pnl = float(latest.get("realized_pnl_usd", 0))
        return pnl <= -(equity * weekly_loss_stop_pct)
    except Exception:
        return False

def score_signals():
    cfg = load_config()

    max_positions = cfg_int(cfg, "max_positions")
    cash_reserve_pct = cfg_float(cfg, "cash_reserve_pct")
    risk_pct_per_trade = cfg_float(cfg, "risk_pct_per_trade")
    max_position_pct = cfg_float(cfg, "max_position_pct")
    block_new_buys_on_high_sell = cfg_bool(cfg, "block_new_buys_on_high_sell")
    weekly_loss_stop_pct = cfg_float(cfg, "weekly_loss_stop_pct")
    momentum_priority_boost = cfg_float(cfg, "momentum_priority_boost")
    quality_position_size_factor = cfg_float(cfg, "quality_position_size_factor")
    add_more_min_return = cfg_float(cfg, "add_more_min_return")
    add_more_min_score = cfg_float(cfg, "add_more_min_score")

    watch = pd.read_csv(WATCHLIST_PATH)
    watch["enabled"] = watch["enabled"].astype(str).str.upper().isin(["TRUE", "YES", "1", "Y"])
    watch = watch[watch["enabled"]]

    market = pd.read_csv(MARKET_PATH)
    market["ticker"] = market["ticker"].astype(str).str.upper().str.strip()

    holdings = pd.read_csv(HOLDINGS_PATH) if HOLDINGS_PATH.exists() else pd.DataFrame()
    if not holdings.empty:
        holdings["ticker"] = holdings["ticker"].astype(str).str.upper().str.strip()
        for col in ["shares", "avg_cost", "holding_return_pct", "market_value"]:
            if col not in holdings.columns:
                holdings[col] = np.nan
    else:
        holdings = pd.DataFrame(columns=["ticker", "shares", "avg_cost", "holding_return_pct", "market_value"])

    position_count = int((holdings["shares"].fillna(0) > 0).sum())
    open_slots = max(max_positions - position_count, 0)

    cash_available_raw = get_cash_available()
    cash_available = max(cash_available_raw * (1 - cash_reserve_pct), 0)

    holdings_value = pd.to_numeric(holdings.get("market_value", 0), errors="coerce").fillna(0).sum()
    equity = cash_available_raw + holdings_value

    risk_budget_usd = equity * risk_pct_per_trade
    max_position_usd = equity * max_position_pct

    weekly_stop = weekly_loss_stop_triggered(equity, weekly_loss_stop_pct)

    df = watch.merge(market, on="ticker", how="left")
    df = df.merge(
        holdings[["ticker", "shares", "avg_cost", "holding_return_pct"]],
        on="ticker",
        how="left"
    )

    rows = []
    provisional_rows = []

    for _, row in df.iterrows():
        price = row.get("price", np.nan)
        tier = str(row.get("tier", "QUALITY")).upper()
        atr = row.get("atr", np.nan)
        holding_return_pct = row.get("holding_return_pct", np.nan)
        shares_held = row.get("shares", 0)
        already_held = pd.notna(shares_held) and shares_held > 0

        trend_score = 0
        if pd.notna(price) and pd.notna(row.get("sma_50")) and price > row["sma_50"]:
            trend_score += 40
        if pd.notna(price) and pd.notna(row.get("sma_200")) and price > row["sma_200"]:
            trend_score += 40

        momentum_score = 0
        if pd.notna(row.get("return_1m")) and row["return_1m"] > 0:
            momentum_score += 25
        if pd.notna(row.get("return_3m")) and row["return_3m"] > 0:
            momentum_score += 35
        if pd.notna(row.get("return_6m")) and row["return_6m"] > 0:
            momentum_score += 40

        accelerator_score = 50
        if pd.notna(row.get("macd_histogram")) and row["macd_histogram"] > 0:
            accelerator_score += 25
        if pd.notna(row.get("volume_trend")) and row["volume_trend"] >= 1.5:
            accelerator_score += 25
        accelerator_score = clamp(accelerator_score)

        rsi = row.get("rsi_14", np.nan)
        rsi_score = 100 if pd.notna(rsi) and 40 <= rsi <= 70 else 50

        final_score = round(
            trend_score * 0.25 +
            momentum_score * 0.30 +
            accelerator_score * 0.25 +
            rsi_score * 0.20
        )

        if tier == "MOMENTUM":
            final_score = clamp(final_score + momentum_priority_boost)

        if tier == "MOMENTUM":
            stop_loss = price - (2 * atr) if pd.notna(price) and pd.notna(atr) and atr > 0 else price * 0.80
            trim_price = price + (3 * atr) if pd.notna(price) and pd.notna(atr) and atr > 0 else price * 1.25
        else:
            stop_loss = price - (1.5 * atr) if pd.notna(price) and pd.notna(atr) and atr > 0 else price * 0.92
            trim_price = price + (2 * atr) if pd.notna(price) and pd.notna(atr) and atr > 0 else price * 1.15

        action = "WATCH"
        if final_score >= 80 and trend_score >= 70:
            action = "BUY"
        elif final_score >= 75:
            action = "BUY SMALL"

        position_rule = ""
        if already_held:
            position_rule = "Already held"
        elif open_slots <= 0:
            position_rule = f"Max {max_positions} positions reached"
            if action in ["BUY", "BUY SMALL"]:
                action = "WATCH"
        else:
            position_rule = f"{open_slots} open slot(s)"

        add_more_signal = ""
        add_more_reason = ""

        if already_held:
            if pd.isna(holding_return_pct):
                add_more_signal = "NO"
                add_more_reason = "Missing holding return"
            elif holding_return_pct < 0:
                add_more_signal = "NO"
                add_more_reason = "Do not average down"
            elif holding_return_pct >= add_more_min_return and final_score >= add_more_min_score and trend_score >= 70:
                add_more_signal = "ADD SMALL"
                add_more_reason = "Winner with strong signal"
            else:
                add_more_signal = "HOLD"
                add_more_reason = "Held, but not strong enough to add"

        exit_action = ""
        exit_priority = ""
        exit_reason = ""

        if already_held:
            if pd.notna(price) and pd.notna(stop_loss) and price <= stop_loss:
                exit_action = "SELL"
                exit_priority = "HIGH"
                exit_reason = "Price at or below stop loss"
            elif pd.notna(holding_return_pct) and holding_return_pct <= -0.15:
                exit_action = "SELL"
                exit_priority = "HIGH"
                exit_reason = "Holding down 15%+"
            elif trend_score < 40 and final_score < 55:
                exit_action = "SELL"
                exit_priority = "MEDIUM"
                exit_reason = "Trend and score weakened"
            elif pd.notna(price) and pd.notna(trim_price) and price >= trim_price:
                exit_action = "TRIM"
                exit_priority = "MEDIUM"
                exit_reason = "Price reached trim target"
            elif pd.notna(rsi) and rsi >= 75 and pd.notna(holding_return_pct) and holding_return_pct > 0:
                exit_action = "TRIM"
                exit_priority = "MEDIUM"
                exit_reason = "RSI overbought while profitable"
            elif final_score < 50:
                exit_action = "REVIEW"
                exit_priority = "LOW"
                exit_reason = "Signal score weakened"
            else:
                exit_action = "HOLD"
                exit_priority = "LOW"
                exit_reason = "No exit trigger"

	sell_signal = exit_action if exit_action in ["SELL", "TRIM", "REVIEW"] else ""

        decision_reasons = []
        warnings = []

        if trend_score >= 70:
            decision_reasons.append("Strong trend")
        if momentum_score >= 70:
            decision_reasons.append("Positive momentum")
        if accelerator_score >= 75:
            decision_reasons.append("MACD/volume acceleration")
        if tier == "MOMENTUM":
            decision_reasons.append("Momentum tier boost")

        if pd.notna(rsi) and rsi > 70:
            warnings.append("RSI overbought")
        if pd.isna(price):
            warnings.append("Missing price")
        if pd.isna(atr) or atr <= 0:
            warnings.append("Missing ATR")
        if open_slots <= 0 and not already_held:
            warnings.append(f"Max {max_positions} positions reached")
        if add_more_signal == "NO":
            warnings.append(add_more_reason)
        if exit_action in ["SELL", "TRIM", "REVIEW"]:
            warnings.append(exit_reason)
        if weekly_stop:
            warnings.append("Weekly loss stop active")
        if cash_reserve_pct > 0:
            warnings.append(f"Cash reserve {cash_reserve_pct:.0%} applied")

        buy_amount_usd = 0.0
        shares_to_buy = 0.0

        can_buy_new = not already_held and open_slots > 0 and action in ["BUY", "BUY SMALL"]
        can_add_more = already_held and add_more_signal == "ADD SMALL" and exit_action not in ["SELL", "TRIM"]

        if weekly_stop:
            can_buy_new = False
            can_add_more = False
            if action in ["BUY", "BUY SMALL"]:
                action = "WATCH"

        provisional_rows.append({
            "ticker": row["ticker"],
            "sector": row.get("sector", ""),
            "tier": tier,
            "price": price,
            "score": final_score,
            "action": action,
            "trend_score": trend_score,
            "momentum_score": momentum_score,
            "accelerator_score": accelerator_score,
            "rsi_14": rsi,
            "gap_pct": row.get("gap_pct", np.nan),
            "volume_trend": row.get("volume_trend", np.nan),
            "macd_histogram": row.get("macd_histogram", np.nan),
            "stop_loss": stop_loss,
            "trim_price": trim_price,
            "atr": atr,
            "risk_budget_usd": round(risk_budget_usd, 2),
            "max_position_usd": round(max_position_usd, 2),
            "holding_return_pct": holding_return_pct,
            "sell_signal": sell_signal,
            "exit_action": exit_action,
            "exit_priority": exit_priority,
            "exit_reason": exit_reason,
            "position_count": position_count,
            "open_slots": open_slots,
            "position_rule": position_rule,
            "add_more_signal": add_more_signal,
            "add_more_reason": add_more_reason,
            "decision_reasons": decision_reasons,
            "warnings": warnings,
            "_can_buy_new": can_buy_new,
            "_can_add_more": can_add_more,
        })

    high_sell_exists = any(
        r["exit_action"] == "SELL" and r["exit_priority"] == "HIGH"
        for r in provisional_rows
    )

    for r in provisional_rows:
        price = r["price"]
        stop_loss = r["stop_loss"]
        tier = r["tier"]
        action = r["action"]

        can_buy_new = r.pop("_can_buy_new")
        can_add_more = r.pop("_can_add_more")

        if block_new_buys_on_high_sell and high_sell_exists and can_buy_new:
            can_buy_new = False
            r["warnings"].append("Blocked: high priority sell exists")
            if action in ["BUY", "BUY SMALL"]:
                action = "WATCH"
                r["action"] = action

        buy_amount_usd = 0.0
        shares_to_buy = 0.0

        if (can_buy_new or can_add_more) and pd.notna(price) and price > 0:
            risk_per_share = max(price - stop_loss, 0) if pd.notna(stop_loss) else 0

            if risk_per_share > 0:
                atr_sized_amount = (risk_budget_usd / risk_per_share) * price
                buy_amount_usd = min(atr_sized_amount, max_position_usd, cash_available)
            else:
                buy_amount_usd = min(max_position_usd, cash_available)

            if tier == "QUALITY":
                buy_amount_usd *= quality_position_size_factor

            if action == "BUY SMALL" or can_add_more:
                buy_amount_usd *= 0.5

            buy_amount_usd = min(buy_amount_usd, cash_available)
            shares_to_buy = buy_amount_usd / price if buy_amount_usd > 0 else 0

        sort_priority = review_priority(
            action=r["action"],
            exit_action=r["exit_action"],
            exit_priority=r["exit_priority"],
            position_rule=r["position_rule"],
        )

        r["sort_priority"] = sort_priority
        r["buy_amount_usd"] = round(buy_amount_usd, 2)
        r["shares_to_buy"] = round(shares_to_buy, 6)
        r["decision_reasons"] = "; ".join(r["decision_reasons"])
        r["warnings"] = "; ".join(r["warnings"])

        rows.append(r)

    out = pd.DataFrame(rows).sort_values(
        ["sort_priority", "score", "ticker"],
        ascending=[True, False, True]
    )

    out.to_csv(SIGNALS_PATH, index=False)
    return out

if __name__ == "__main__":
    score_signals()
