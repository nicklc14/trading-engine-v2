import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path("data")
SIGNALS_PATH = DATA_DIR / "signals.csv"
MARKET_PATH = DATA_DIR / "market_data.csv"
WATCHLIST_PATH = DATA_DIR / "watchlist.csv"
CASH_PATH = DATA_DIR / "cash.csv"

RISK_PCT_PER_TRADE = 0.02
MAX_POSITION_PCT = 0.25

def clamp(x, lo=0, hi=100):
    return max(lo, min(hi, x))

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

def score_signals():
    watch = pd.read_csv(WATCHLIST_PATH)
    watch["enabled"] = watch["enabled"].astype(str).str.upper().isin(["TRUE", "YES", "1", "Y"])
    watch = watch[watch["enabled"]]

    market = pd.read_csv(MARKET_PATH)
    market["ticker"] = market["ticker"].astype(str).str.upper().str.strip()

    cash_available = get_cash_available()
    risk_budget_usd = cash_available * RISK_PCT_PER_TRADE
    max_position_usd = cash_available * MAX_POSITION_PCT

    df = watch.merge(market, on="ticker", how="left")
    rows = []

    for _, row in df.iterrows():
        price = row.get("price", np.nan)
        tier = row.get("tier", "QUALITY")
        atr = row.get("atr", np.nan)

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

        decision_reasons = []
        warnings = []

        if trend_score >= 70:
            decision_reasons.append("Strong trend")
        if momentum_score >= 70:
            decision_reasons.append("Positive momentum")
        if accelerator_score >= 75:
            decision_reasons.append("MACD/volume acceleration")
        if pd.notna(rsi) and rsi > 70:
            warnings.append("RSI overbought")
        if pd.isna(price):
            warnings.append("Missing price")
        if pd.isna(atr) or atr <= 0:
            warnings.append("Missing ATR")

        buy_amount_usd = 0.0
        shares_to_buy = 0.0

        if action in ["BUY", "BUY SMALL"] and pd.notna(price) and price > 0:
            risk_per_share = max(price - stop_loss, 0) if pd.notna(stop_loss) else 0
            if risk_per_share > 0:
                atr_sized_amount = (risk_budget_usd / risk_per_share) * price
                buy_amount_usd = min(atr_sized_amount, max_position_usd, cash_available)
                if action == "BUY SMALL":
                    buy_amount_usd *= 0.5
            else:
                buy_amount_usd = min(max_position_usd, cash_available)

            shares_to_buy = buy_amount_usd / price if buy_amount_usd > 0 else 0

        rows.append({
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
            "buy_amount_usd": round(buy_amount_usd, 2),
            "shares_to_buy": round(shares_to_buy, 6),
            "risk_budget_usd": round(risk_budget_usd, 2),
            "max_position_usd": round(max_position_usd, 2),
            "decision_reasons": "; ".join(decision_reasons),
            "warnings": "; ".join(warnings)
        })

    out = pd.DataFrame(rows).sort_values("score", ascending=False)
    out.to_csv(SIGNALS_PATH, index=False)
    return out

if __name__ == "__main__":
    score_signals()
