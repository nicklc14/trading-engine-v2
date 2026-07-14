import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path("data")
SIGNALS_PATH = DATA_DIR / "signals.csv"
PREMARKET_PATH = DATA_DIR / "premarket_signals.csv"

def score_premarket_signals():
    signals = pd.read_csv(SIGNALS_PATH)
    rows = []

    for _, row in signals.iterrows():
        ticker = row["ticker"]
        tier = row.get("tier", "QUALITY")
        price = row.get("price", np.nan)
        gap_pct = row.get("gap_pct", np.nan)
        volume_trend = row.get("volume_trend", np.nan)
        macd_hist = row.get("macd_histogram", np.nan)
        rsi = row.get("rsi_14", np.nan)

        premarket_score = 50
        tags = []

        gap_reason = "No meaningful gap"
        if pd.notna(gap_pct):
            if gap_pct > 0.10:
                premarket_score += 35
                gap_reason = "Huge gap up >10%"
                tags.append("huge_gap_up")
            elif gap_pct > 0.05:
                premarket_score += 25
                gap_reason = "Strong gap up >5%"
                tags.append("strong_gap_up")
            elif gap_pct > 0.03:
                premarket_score += 15
                gap_reason = "Valid gap up >3%"
                tags.append("gap_up")
            elif gap_pct < -0.03:
                premarket_score -= 30
                gap_reason = "Gap down below -3%"
                tags.append("gap_down")

        volume_reason = "Volume not confirming"
        if pd.notna(volume_trend):
            if volume_trend >= 2.0:
                premarket_score += 25
                volume_reason = "Very strong volume >=2.0x"
                tags.append("very_strong_volume")
            elif volume_trend >= 1.5:
                premarket_score += 15
                volume_reason = "Volume confirmation >=1.5x"
                tags.append("volume_confirmed")
            elif volume_trend < 0.7:
                premarket_score -= 15
                volume_reason = "Weak volume <0.7x"
                tags.append("weak_volume")

        macd_reason = "MACD not confirming"
        if pd.notna(macd_hist):
            if macd_hist > 0:
                premarket_score += 10
                macd_reason = "MACD histogram positive"
                tags.append("macd_positive")
            else:
                premarket_score -= 10
                macd_reason = "MACD histogram negative"
                tags.append("macd_negative")

        rsi_reason = "RSI neutral/unknown"
        if pd.notna(rsi):
            if 40 <= rsi <= 70:
                premarket_score += 10
                rsi_reason = "RSI healthy 40–70"
                tags.append("rsi_healthy")
            elif rsi > 80:
                premarket_score -= 15
                rsi_reason = "RSI overbought >80"
                tags.append("rsi_overbought")
            elif rsi < 30:
                premarket_score -= 15
                rsi_reason = "RSI oversold <30"
                tags.append("rsi_oversold")

        premarket_score = max(0, min(100, round(premarket_score)))

        premarket_action = "SKIP"
        buy_amount = 0
        position_rationale = "Skip — setup does not meet premarket rules"

        if tier == "MOMENTUM" and pd.notna(gap_pct) and gap_pct > 0.03:
            if premarket_score >= 75:
                premarket_action = "PREMARKET BUY"
                buy_amount = 20 if premarket_score >= 85 else 12
                position_rationale = "Buy — momentum tier with valid gap and sufficient premarket score"
            elif premarket_score >= 70:
                premarket_action = "PREMARKET WATCH"
                position_rationale = "Watch — close to buy threshold but needs stronger confirmation"

        shares_to_buy = buy_amount / price if buy_amount > 0 and pd.notna(price) and price > 0 else 0

        rows.append({
            "ticker": ticker,
            "tier": tier,
            "price": price,
            "gap_pct": gap_pct,
            "volume_trend": volume_trend,
            "premarket_score": premarket_score,
            "premarket_action": premarket_action,
            "buy_amount_usd": buy_amount,
            "shares_to_buy": shares_to_buy,
            "stop_loss": row.get("stop_loss", np.nan),
            "trim_price": row.get("trim_price", np.nan),
            "reason_tags": "; ".join(tags),
            "position_rationale": position_rationale,
            "gap_reason": gap_reason,
            "volume_reason": volume_reason,
            "macd_reason": macd_reason,
            "rsi_reason": rsi_reason,
        })

    out = pd.DataFrame(rows).sort_values("premarket_score", ascending=False)
    out.to_csv(PREMARKET_PATH, index=False)
    return out

if __name__ == "__main__":
    score_premarket_signals()
