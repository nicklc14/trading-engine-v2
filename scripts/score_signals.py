import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

DATA_DIR = Path("data")
SIGNALS_PATH = DATA_DIR / "signals.csv"
MARKET_PATH = DATA_DIR / "market_data.csv"
DASHBOARD_WATCHLIST_PATH = DATA_DIR / "dashboard_watchlist.csv"
CASH_PATH = DATA_DIR / "cash.csv"
HOLDINGS_PATH = DATA_DIR / "holdings.csv"
CONFIG_PATH = DATA_DIR / "config.csv"
SEC_EVENTS_PATH = DATA_DIR / "sec_events.csv"
REGIME_PATH = DATA_DIR / "market_regime.csv"
TRADES_PATH = DATA_DIR / "trades.csv"

def clamp(x, lo=0, hi=100):
    return max(lo, min(hi, x))

def truthy(x):
    return str(x).strip().upper() in ["TRUE", "YES", "1", "Y"]

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
        "max_moonshot_positions": 2,
        "moonshot_score_boost": 8,
        "moonshot_position_size_factor": 0.50,
        "moonshot_add_min_return": 0.15,
        "moonshot_stop_atr_multiplier": 2.5,
        "moonshot_trim_atr_multiplier": 4.0,
        "risk_off_score_penalty": 8,
        "risk_off_position_size_factor": 0.50,
        "risk_off_buy_threshold": 85,
        "risk_off_buy_small_threshold": 80,
        "risk_off_block_new_moonshots": "TRUE",
        "aggressive_mode": "TRUE",
        "aggressive_risk_on_score_boost": 3,
        "aggressive_risk_on_position_size_factor": 1.25,
        "aggressive_risk_on_buy_threshold": 78,
        "aggressive_risk_on_buy_small_threshold": 73,
        "reentry_lookback_days": 60,
        "reentry_min_score": 70,
        "reentry_min_momentum_score": 70,
        "reentry_block_stop_loss_sells": "TRUE",
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
    return truthy(cfg.get(key, False))

def load_market_regime():
    if not REGIME_PATH.exists():
        return "UNKNOWN"
    regime = pd.read_csv(REGIME_PATH)
    if regime.empty or "market_regime" not in regime.columns:
        return "UNKNOWN"
    return str(regime["market_regime"].iloc[0]).strip()

def get_cash_available():
    if not CASH_PATH.exists():
        return 0.0
    cash = pd.read_csv(CASH_PATH)
    return float(cash["cash_available_usd"].iloc[0]) if not cash.empty else 0.0

def load_recent_sells(lookback_days):
    if not TRADES_PATH.exists():
        return {}

    trades = pd.read_csv(TRADES_PATH)
    if trades.empty:
        return {}

    trades["date"] = pd.to_datetime(trades["date"], errors="coerce")
    trades["ticker"] = trades["ticker"].astype(str).str.upper().str.strip()
    trades["type_upper"] = trades["type"].astype(str).str.upper().str.strip()
    trades["price"] = pd.to_numeric(trades.get("price", np.nan), errors="coerce")

    today = pd.Timestamp(datetime.utcnow().date())
    cutoff = today - pd.Timedelta(days=lookback_days)

    sells = trades[
        (trades["type_upper"] == "SELL")
        & (trades["date"].notna())
        & (trades["date"] >= cutoff)
        & (trades["ticker"] != "")
    ].copy()

    if sells.empty:
        return {}

    sells = sells.sort_values(["ticker", "date"])
    latest = sells.groupby("ticker").tail(1)

    out = {}
    for _, row in latest.iterrows():
        out[row["ticker"]] = {
            "sell_date": row.get("date"),
            "sell_price": row.get("price", np.nan),
            "sell_note": str(row.get("notes", "")),
        }

    return out

def prior_sell_blocks_reentry(sell_note):
    note = str(sell_note).lower()
    block_terms = [
        "stop loss",
        "broken trend",
        "trend weakened",
        "score weakened",
        "holding down",
        "down 15",
    ]
    return any(term in note for term in block_terms)

def get_weekly_realized_pnl():
    if not TRADES_PATH.exists():
        return 0.0

    trades = pd.read_csv(TRADES_PATH)
    if trades.empty:
        return 0.0

    trades["date"] = pd.to_datetime(trades["date"], errors="coerce")
    trades["type_upper"] = trades["type"].astype(str).str.upper().str.strip()

    today = pd.Timestamp(datetime.utcnow().date())
    week_start = today.to_period("W").start_time
    sells = trades[(trades["type_upper"] == "SELL") & (trades["date"] >= week_start)]

    realized_pnl = 0.0

    for _, sell in sells.iterrows():
        ticker = str(sell["ticker"]).upper().strip()
        holding_key = str(sell.get("holding_key", "")).strip()

        buys = trades[
            (trades["type_upper"] == "BUY")
            & (trades["ticker"].astype(str).str.upper().str.strip() == ticker)
            & (trades["holding_key"].astype(str).str.strip() == holding_key)
        ]

        buy_cost = pd.to_numeric(buys.get("usd_amount", 0), errors="coerce").fillna(0).sum()
        sell_proceeds = pd.to_numeric(pd.Series([sell.get("usd_amount", 0)]), errors="coerce").fillna(0).iloc[0]
        realized_pnl += sell_proceeds - buy_cost

    return float(realized_pnl)

def review_priority(action, exit_action="", exit_priority="", position_rule=""):
    rule = str(position_rule).upper()

    if exit_action == "SELL" and exit_priority == "HIGH":
        return 1
    if exit_action == "SELL":
        return 2
    if "ALREADY HELD" in rule:
        return 3
    if "RE-ENTRY" in rule and action == "BUY":
        return 4
    if action == "BUY":
        return 5
    if "RE-ENTRY" in rule and action == "BUY SMALL":
        return 6
    if action == "BUY SMALL":
        return 7
    if action == "WATCH":
        return 8
    return 9

def score_signals():
    cfg = load_config()
    market_regime = load_market_regime()
    is_risk_on = market_regime.upper() == "RISK ON"
    is_risk_off = market_regime.upper() == "RISK OFF"

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
    max_moonshot_positions = cfg_int(cfg, "max_moonshot_positions")
    moonshot_score_boost = cfg_float(cfg, "moonshot_score_boost")
    moonshot_position_size_factor = cfg_float(cfg, "moonshot_position_size_factor")
    moonshot_add_min_return = cfg_float(cfg, "moonshot_add_min_return")
    moonshot_stop_atr_multiplier = cfg_float(cfg, "moonshot_stop_atr_multiplier")
    moonshot_trim_atr_multiplier = cfg_float(cfg, "moonshot_trim_atr_multiplier")

    risk_off_score_penalty = cfg_float(cfg, "risk_off_score_penalty")
    risk_off_position_size_factor = cfg_float(cfg, "risk_off_position_size_factor")
    risk_off_buy_threshold = cfg_float(cfg, "risk_off_buy_threshold")
    risk_off_buy_small_threshold = cfg_float(cfg, "risk_off_buy_small_threshold")
    risk_off_block_new_moonshots = cfg_bool(cfg, "risk_off_block_new_moonshots")

    aggressive_mode = cfg_bool(cfg, "aggressive_mode")
    aggressive_score_boost = cfg_float(cfg, "aggressive_risk_on_score_boost")
    aggressive_size_factor = cfg_float(cfg, "aggressive_risk_on_position_size_factor")
    aggressive_buy_threshold = cfg_float(cfg, "aggressive_risk_on_buy_threshold")
    aggressive_buy_small_threshold = cfg_float(cfg, "aggressive_risk_on_buy_small_threshold")

    reentry_lookback_days = cfg_int(cfg, "reentry_lookback_days")
    reentry_min_score = cfg_float(cfg, "reentry_min_score")
    reentry_min_momentum_score = cfg_float(cfg, "reentry_min_momentum_score")
    reentry_block_stop_loss_sells = cfg_bool(cfg, "reentry_block_stop_loss_sells")
    recent_sells = load_recent_sells(reentry_lookback_days)

    buy_threshold = 80
    buy_small_threshold = 75

    if is_risk_off:
        buy_threshold = risk_off_buy_threshold
        buy_small_threshold = risk_off_buy_small_threshold
    elif is_risk_on and aggressive_mode:
        buy_threshold = aggressive_buy_threshold
        buy_small_threshold = aggressive_buy_small_threshold

    watch = pd.read_csv(DASHBOARD_WATCHLIST_PATH)
    watch["enabled"] = watch["enabled"].astype(str).str.upper().isin(["TRUE", "YES", "1", "Y"])
    watch["ticker"] = watch["ticker"].astype(str).str.upper().str.strip()
    watch = watch[watch["enabled"]]

    market = pd.read_csv(MARKET_PATH)
    market["ticker"] = market["ticker"].astype(str).str.upper().str.strip()

    holdings = pd.read_csv(HOLDINGS_PATH) if HOLDINGS_PATH.exists() else pd.DataFrame()
    if holdings.empty:
        holdings = pd.DataFrame(columns=["ticker", "shares", "holding_return_pct", "market_value"])

    holdings["ticker"] = holdings["ticker"].astype(str).str.upper().str.strip()
    for col in ["shares", "holding_return_pct", "market_value"]:
        if col not in holdings.columns:
            holdings[col] = np.nan

    sec_events = pd.read_csv(SEC_EVENTS_PATH) if SEC_EVENTS_PATH.exists() else pd.DataFrame()
    if not sec_events.empty:
        sec_events["ticker"] = sec_events["ticker"].astype(str).str.upper().str.strip()
    else:
        sec_events = pd.DataFrame(columns=[
            "ticker", "sec_event_flag", "sec_event_type", "sec_event_date",
            "sec_form", "sec_severity", "sec_score_adjustment", "sec_event_note",
        ])

    position_count = int((holdings["shares"].fillna(0) > 0).sum())
    open_slots = max(max_positions - position_count, 0)

    raw_cash = get_cash_available()
    cash_available = max(raw_cash * (1 - cash_reserve_pct), 0)
    holdings_value = pd.to_numeric(holdings["market_value"], errors="coerce").fillna(0).sum()
    equity = raw_cash + holdings_value

    weekly_realized_pnl = get_weekly_realized_pnl()
    weekly_loss_stop_usd = equity * weekly_loss_stop_pct
    weekly_loss_stop_triggered = weekly_loss_stop_pct > 0 and weekly_realized_pnl <= -weekly_loss_stop_usd

    risk_budget_usd = equity * risk_pct_per_trade
    max_position_usd = equity * max_position_pct

    if is_risk_off:
        risk_budget_usd *= risk_off_position_size_factor
        max_position_usd *= risk_off_position_size_factor
    elif is_risk_on and aggressive_mode:
        risk_budget_usd *= aggressive_size_factor
        max_position_usd *= aggressive_size_factor

    df = watch.merge(market, on="ticker", how="left")
    df = df.merge(holdings[["ticker", "shares", "holding_return_pct"]], on="ticker", how="left")
    df = df.merge(sec_events, on="ticker", how="left")

    moonshot_position_count = int(((df["tier"].astype(str).str.upper() == "MOONSHOT") & (pd.to_numeric(df["shares"], errors="coerce").fillna(0) > 0)).sum())
    moonshot_open_slots = max(max_moonshot_positions - moonshot_position_count, 0)

    rows = []

    for _, row in df.iterrows():
        ticker = row["ticker"]
        tier = str(row.get("tier", "QUALITY")).upper()
        price = row.get("price", np.nan)
        atr = row.get("atr", np.nan)
        rsi = row.get("rsi_14", np.nan)
        atr_pct = row.get("atr_pct", np.nan)
        shares_held = row.get("shares", 0)
        holding_return_pct = row.get("holding_return_pct", np.nan)
        already_held = pd.notna(shares_held) and shares_held > 0
        recently_sold = ticker in recent_sells and not already_held

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

        rsi_score = 100 if pd.notna(rsi) and 40 <= rsi <= 70 else 50

        final_score = round(trend_score * 0.25 + momentum_score * 0.30 + accelerator_score * 0.25 + rsi_score * 0.20)

        if tier == "MOMENTUM":
            final_score = clamp(final_score + momentum_priority_boost)
        if tier == "MOONSHOT":
            final_score = clamp(final_score + moonshot_score_boost)

        sec_score_adjustment = pd.to_numeric(row.get("sec_score_adjustment", 0), errors="coerce")
        if pd.isna(sec_score_adjustment):
            sec_score_adjustment = 0
        final_score = clamp(final_score + sec_score_adjustment)

        if is_risk_off and not already_held:
            final_score = clamp(final_score - risk_off_score_penalty)
        elif is_risk_on and aggressive_mode and not already_held:
            final_score = clamp(final_score + aggressive_score_boost)

        if tier == "MOONSHOT":
            stop_loss = price - (moonshot_stop_atr_multiplier * atr) if pd.notna(price) and pd.notna(atr) and atr > 0 else price * 0.75
            trim_price = price + (moonshot_trim_atr_multiplier * atr) if pd.notna(price) and pd.notna(atr) and atr > 0 else price * 1.40
        elif tier == "MOMENTUM":
            stop_loss = price - (2 * atr) if pd.notna(price) and pd.notna(atr) and atr > 0 else price * 0.80
            trim_price = price + (3 * atr) if pd.notna(price) and pd.notna(atr) and atr > 0 else price * 1.25
        else:
            stop_loss = price - (1.5 * atr) if pd.notna(price) and pd.notna(atr) and atr > 0 else price * 0.92
            trim_price = price + (2 * atr) if pd.notna(price) and pd.notna(atr) and atr > 0 else price * 1.15

        action = "WATCH"
        if final_score >= buy_threshold and trend_score >= 70:
            action = "BUY"
        elif final_score >= buy_small_threshold:
            action = "BUY SMALL"

        if is_risk_off and tier == "MOONSHOT" and not already_held and risk_off_block_new_moonshots:
            action = "WATCH"

        reentry_setup = False
        reentry_blocked = False

        if recently_sold:
            sell_info = recent_sells.get(ticker, {})
            reentry_blocked = reentry_block_stop_loss_sells and prior_sell_blocks_reentry(sell_info.get("sell_note", ""))
            reentry_setup = (
                final_score >= reentry_min_score
                and (
                    momentum_score >= reentry_min_momentum_score
                    or trend_score >= 70
                    or accelerator_score >= 75
                )
                and not reentry_blocked
            )

        if recently_sold and reentry_blocked:
            action = "WATCH"

        if already_held:
            position_rule = "Already held"
        elif open_slots <= 0:
            position_rule = f"Re-entry watch; Max {max_positions} positions reached" if reentry_setup else f"Max {max_positions} positions reached"
            action = "WATCH"
        elif tier == "MOONSHOT" and moonshot_open_slots <= 0:
            position_rule = f"Re-entry watch; Max {max_moonshot_positions} MOONSHOT positions reached" if reentry_setup else f"Max {max_moonshot_positions} MOONSHOT positions reached"
            action = "WATCH"
        elif reentry_setup and action in ["BUY", "BUY SMALL"]:
            position_rule = f"Re-entry candidate; {open_slots} open slot(s)"
        elif recently_sold:
            position_rule = f"Re-entry watch; {open_slots} open slot(s)"
        else:
            position_rule = f"{open_slots} open slot(s); {moonshot_open_slots} MOONSHOT slot(s)" if tier == "MOONSHOT" else f"{open_slots} open slot(s)"

        add_more_signal = ""
        add_more_reason = ""

        if already_held:
            if pd.isna(holding_return_pct):
                add_more_signal = "NO"
                add_more_reason = "Missing holding return"
            elif holding_return_pct < 0:
                add_more_signal = "NO"
                add_more_reason = "Do not average down"
            elif tier == "MOONSHOT" and holding_return_pct < moonshot_add_min_return:
                add_more_signal = "NO"
                add_more_reason = f"MOONSHOT add blocked until return is above {moonshot_add_min_return:.0%}"
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
                exit_action = "SELL"; exit_priority = "HIGH"; exit_reason = "Price at or below stop loss"
            elif tier == "MOONSHOT" and pd.notna(holding_return_pct) and holding_return_pct <= -0.15:
                if final_score >= 75:
                    exit_action = "HOLD"; exit_priority = "LOW"; exit_reason = "Moonshot down 15%+, but score still strong"
                elif final_score >= 65:
                    exit_action = "REVIEW"; exit_priority = "MEDIUM"; exit_reason = "Moonshot down 15%+; review before selling"
                else:
                    exit_action = "SELL"; exit_priority = "HIGH"; exit_reason = "Moonshot down 15%+ and score weakened"
            elif pd.notna(holding_return_pct) and holding_return_pct <= -0.15:
                exit_action = "SELL"; exit_priority = "HIGH"; exit_reason = "Holding down 15%+"
            elif trend_score < 40 and final_score < 55:
                exit_action = "SELL"; exit_priority = "MEDIUM"; exit_reason = "Trend and score weakened"
            elif pd.notna(price) and pd.notna(trim_price) and price >= trim_price:
                exit_action = "TRIM"; exit_priority = "MEDIUM"; exit_reason = "Price reached trim target"
            elif pd.notna(rsi) and rsi >= 75 and pd.notna(holding_return_pct) and holding_return_pct > 0:
                exit_action = "TRIM"; exit_priority = "MEDIUM"; exit_reason = "RSI overbought while profitable"
            else:
                exit_action = "HOLD"; exit_priority = "LOW"; exit_reason = "No exit trigger"

        sell_signal = exit_action if exit_action in ["SELL", "TRIM", "REVIEW"] else ""

        warnings = []
        reasons = []

        if market_regime != "UNKNOWN":
            reasons.append(f"Market regime: {market_regime}")
        else:
            warnings.append("Market regime unknown")

        if is_risk_on and aggressive_mode:
            reasons.append("Aggressive mode active")
        if is_risk_off:
            warnings.append("Risk Off: stricter buy rules and smaller sizing applied")
        if weekly_loss_stop_triggered:
            warnings.append(f"Weekly loss stop active: weekly realized P&L ${weekly_realized_pnl:.2f}")

        if trend_score >= 70:
            reasons.append("Strong trend")
        if momentum_score >= 70:
            reasons.append("Positive momentum")
        if accelerator_score >= 75:
            reasons.append("MACD/volume acceleration")
        if reentry_setup:
            reasons.append("Re-entry setup")
        if recently_sold and reentry_blocked:
            warnings.append("Re-entry blocked by prior sell reason")
        elif recently_sold and not reentry_setup:
            warnings.append("Re-entry watch")
        if tier == "MOMENTUM":
            reasons.append("Momentum tier boost")
        if tier == "MOONSHOT":
            reasons.append("Moonshot tier boost")

        if pd.notna(rsi) and rsi > 70:
            warnings.append("RSI overbought")
        if pd.isna(price):
            warnings.append("Missing price")
        if pd.isna(atr) or atr <= 0:
            warnings.append("Missing ATR")
        if add_more_signal == "NO":
            warnings.append(add_more_reason)
        if exit_action in ["SELL", "TRIM", "REVIEW"]:
            warnings.append(exit_reason)
        if tier == "MOONSHOT":
            warnings.append("Moonshot: high risk / small size")
        if tier == "MOONSHOT" and pd.notna(atr_pct) and atr_pct < 0.08:
            warnings.append("Moonshot volatility may be too low")

        rows.append({
            "ticker": ticker,
            "sector": row.get("sector", ""),
            "tier": tier,
            "market_regime": market_regime,
            "aggressive_mode_active": bool(is_risk_on and aggressive_mode),
            "price": price,
            "score": final_score,
            "sort_priority": review_priority(action, exit_action, exit_priority, position_rule),
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
            "buy_amount_usd": 0.0,
            "shares_to_buy": 0.0,
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
            "already_held": already_held,
            "weekly_realized_pnl": round(weekly_realized_pnl, 2),
            "weekly_loss_stop_triggered": weekly_loss_stop_triggered,
            "decision_reasons": "; ".join(reasons),
            "warnings": "; ".join(warnings),
        })

    high_priority_sell_exists = any(r["exit_action"] == "SELL" and r["exit_priority"] == "HIGH" for r in rows)

    block_new_risk = False
    block_reasons = []

    if block_new_buys_on_high_sell and high_priority_sell_exists:
        block_new_risk = True
        block_reasons.append("New buys blocked while HIGH priority SELL exists")

    if weekly_loss_stop_triggered:
        block_new_risk = True
        block_reasons.append(f"New buys blocked by weekly loss stop (${weekly_realized_pnl:.2f})")

    for r in rows:
        already_held = bool(r["already_held"])

        if block_new_risk and r["action"] in ["BUY", "BUY SMALL"]:
            r["action"] = "WATCH"
            r["warnings"] = "; ".join([x for x in [r["warnings"], *block_reasons] if x])
            if not already_held:
                r["position_rule"] = "; ".join([r["position_rule"], *block_reasons])

        can_buy = not already_held and open_slots > 0 and r["action"] in ["BUY", "BUY SMALL"]
        can_add = already_held and r["add_more_signal"] == "ADD SMALL" and r["exit_action"] not in ["SELL", "TRIM"]

        if block_new_risk:
            can_buy = False
            can_add = False

        if r["tier"] == "MOONSHOT" and not already_held and moonshot_open_slots <= 0:
            can_buy = False

        price = r["price"]
        stop_loss = r["stop_loss"]

        if (can_buy or can_add) and pd.notna(price) and price > 0:
            risk_per_share = max(price - stop_loss, 0) if pd.notna(stop_loss) else 0

            if risk_per_share > 0:
                atr_sized_amount = (risk_budget_usd / risk_per_share) * price
                buy_amount_usd = min(atr_sized_amount, max_position_usd, cash_available)
            else:
                buy_amount_usd = min(max_position_usd, cash_available)

            if r["tier"] == "QUALITY":
                buy_amount_usd *= quality_position_size_factor
            if r["tier"] == "MOONSHOT":
                buy_amount_usd *= moonshot_position_size_factor
            if r["action"] == "BUY SMALL" or can_add:
                buy_amount_usd *= 0.5

            buy_amount_usd = min(buy_amount_usd, cash_available)
            r["buy_amount_usd"] = round(buy_amount_usd, 2)
            r["shares_to_buy"] = round(buy_amount_usd / price, 6) if buy_amount_usd > 0 else 0.0

        r["sort_priority"] = review_priority(r["action"], r["exit_action"], r["exit_priority"], r["position_rule"])
        del r["already_held"]

    out = pd.DataFrame(rows).sort_values(
        ["sort_priority", "score", "ticker"],
        ascending=[True, False, True]
    )

    out.to_csv(SIGNALS_PATH, index=False)
    return out

if __name__ == "__main__":
    score_signals()
