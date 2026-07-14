import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path("data")
SIGNALS_PATH = DATA_DIR / "signals.csv"
MARKET_PATH = DATA_DIR / "market_data.csv"
WATCHLIST_PATH = DATA_DIR / "watchlist.csv"
CASH_PATH = DATA_DIR / "cash.csv"

RISK_PER_TRADE_PCT = 0.02
MAX_POSITION_PCT = 0.25

def clamp(x, lo=0, hi=100):
    return max(lo, min(hi, x))

def get_cash_available():
    if not CASH_PATH.exists():
        return 0
    cash = pd.read_csv(CASH_PATH)
    if cash.empty or "cash_available_usd" not in cash.columns:
        return 0
    return float(cash["cash_available_usd"].iloc[0])

def score_signals():
    cash_available = get_cash_available()

    watch = pd.read_csv(WATCHLIST_PATH)
    watch["enabled"] = watch["enabled"].astype(str).str.upper().isin(["TRUE", "YES", "1", "Y"])
    watch = watch[watch["enabled"]]

    market = pd.read_csv(MARKET_PATH)
    market["ticker"] = market["ticker"].astype(str).str.upper().str.strip()

    df = watch.merge(market, on="ticker", how="left")

    rows = []

    for _, row in df.iterrows():
        ticker = row["ticker"]
        price = row.get("price", np.nan)
        tier = row.get("tier", "QUALITY")
        atr = row.get("atr", np.nan)
        volume_trend = row.get("volume_trend", np.nan)
        rsi = row.get("rsi_14", np.nan)
        gap_pct = row.get("gap_pct", np.nan)

        reasons = []
        warnings = []

        if pd.isna(price) or price <= 0:
            warnings.append("Missing price")
        if pd.isna(volume_trend):
            warnings.append("Missing volume trend")
        if pd.isna(atr):
            warnings.append("Missing ATR")
        if pd.isna(rsi):
            warnings.append("Missing RSI")

        trend_score = 0
        if pd.notna(price) and pd.notna(row.get("sma_50")) and price > row["sma_50"]:
            trend_score += 40
            reasons.append("Above 50 SMA")
        if pd.notna(price) and pd.notna(row.get("sma_200")) and price > row["sma_200"]:
            trend_score += 40
            reasons.append("Above 200 SMA")

        momentum_score = 0
        if pd.notna(row.get("return_1m")) and row["return_1m"] > 0:
            momentum_score += 25
            reasons.append("Positive 1M return")
        if pd.notna(row.get("return_3m")) and row["return_3m"] > 0:
            momentum_score += 35
            reasons.append("Positive 3M return")
        if pd.notna(row.get("return_6m")) and row["return_6m"] > 0:
            momentum_score += 40
            reasons.append("Positive 6M return")

        accelerator_score = 50
        if pd.notna(row.get("macd_histogram")) and row["macd_histogram"] > 0:
            accelerator_score += 25
            reasons.append("MACD improving")
        if pd.notna(volume_trend) and volume_trend >= 1.5:
            accelerator_score += 25
            reasons.append("Volume surge")

        accelerator_score = clamp(accelerator_score)

        if pd.notna(rsi):
            if 45 <= rsi <= 70:
                rsi_score = 100
                reasons.append("RSI in momentum zone")
            elif rsi > 80:
                rsi_score = 35
                warnings.append("RSI very extended")
            elif rsi < 35:
                rsi_score = 40
                warnings.append("RSI weak")
            else:
                rsi_score = 60
        else:
            rsi_score = 50

        final_score = round(
            trend_score * 0.25 +
            momentum_score * 0.30 +
            accelerator_score * 0.25 +
            rsi_score * 0.20
        )

        if pd.notna(price) and pd.notna(atr) and atr > 0:
            if tier == "MOMENTUM":
                stop_loss = price - (2.0 * atr)
            else:
                stop_loss = price - (1.5 * atr)
        else:
            stop_loss = price * 0.80 if tier == "MOMENTUM" and pd.notna(price) else price * 0.92 if pd.notna(price) else np.nan

        trim_price = price + (2 * (price - stop_loss)) if pd.notna(price) and pd.notna(stop_loss) else np.nan

        action = "WATCH"
        if final_score >= 80 and trend_score >= 70 and len(warnings) == 0:
            action = "BUY"
        elif final_score >= 75 and "Missing price" not in warnings:
            action = "BUY SMALL"

        risk_per_trade = cash_available * RISK_PER_TRADE_PCT
        max_position = cash_available * MAX_POSITION_PCT

        risk_per_share = price - stop_loss if pd.notna(price) and pd.notna(stop_loss) else np.nan

        if action in ["BUY", "BUY SMALL"] and pd.notna(risk_per_share) and risk_per_share > 0:
            risk_based_amount = risk_per_trade / risk_per_share * price
            buy_amount_usd = min(risk_based_amount, max_position, cash_available)
            if action == "BUY SMALL":
                buy_amount_usd *= 0.5
        else:
            buy_amount_usd = 0

        shares_to_buy = buy_amount_usd / price if pd.notna(price) and price > 0 else 0

        rows.append({
            "ticker": ticker,
            "sector": row.get("sector", ""),
            "tier": tier,
            "price": price,
            "score": final_score,
            "action": action,
            "trend_score": trend_score,
            "momentum_score": momentum_score,
            "accelerator_score": accelerator_score,
            "rsi_14": rsi,
            "gap_pct": gap_pct,
            "volume_trend": volume_trend,
            "macd_histogram": row.get("macd_histogram", np.nan),
            "atr": atr,
            "stop_loss": stop_loss,
            "trim_price": trim_price,
            "buy_amount_usd": round(buy_amount_usd, 2),
            "shares_to_buy": shares_to_buy,
            "decision_reasons": "; ".join(reasons),
            "warnings": "; ".join(warnings)
        })

    out = pd.DataFrame(rows).sort_values("score", ascending=False)
    out.to_csv(SIGNALS_PATH, index=False)
    return out

if __name__ == "__main__":
    score_signals()
