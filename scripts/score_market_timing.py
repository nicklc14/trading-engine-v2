import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path("data")
SIGNALS_PATH = DATA_DIR / "signals.csv"
MARKET_TIMING_PATH = DATA_DIR / "market_timing.csv"

def score_market_timing():
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
        market_regime = row.get("market_regime", "UNKNOWN")

        timing_score = 50
        tags = []

        gap_reason = "No meaningful daily gap"
        if pd.notna(gap_pct):
            if gap_pct > 0.1:
                timing_score += 35
                gap_reason = "Huge daily gap up >10%"
                tags.append("huge_gap_up")
            elif gap_pct > 0.05:
                timing_score += 25
                gap_reason = "Strong daily gap up >5%"
                tags.append("strong_gap_up")
            elif gap_pct > 0.03:
                timing_score += 15
                gap_reason = "Valid daily gap up >3%"
                tags.append("gap_up")
            elif gap_pct < -0.03:
                timing_score -= 30
                gap_reason = "Daily gap down below -3%"
                tags.append("gap_down")

        volume_reason = "Volume not confirming"
        if pd.notna(volume_trend):
            if volume_trend >= 2:
                timing_score += 25
                volume_reason = "Very strong volume >=2.0x"
                tags.append("very_strong_volume")
            elif volume_trend >= 1.5:
                timing_score += 15
                volume_reason = "Volume confirmation >=1.5x"
                tags.append("volume_confirmed")
            elif volume_trend < 0.7:
                timing_score -= 15
                volume_reason = "Weak volume <0.7x"
                tags.append("weak_volume")

        macd_reason = "MACD not confirming"
        if pd.notna(macd_hist):
            if macd_hist > 0:
                timing_score += 10
                macd_reason = "MACD histogram positive"
                tags.append("macd_positive")
            else:
                timing_score -= 10
                macd_reason = "MACD histogram negative"
                tags.append("macd_negative")

        rsi_reason = "RSI neutral/unknown"
        if pd.notna(rsi):
            if 40 <= rsi <= 70:
                timing_score += 10
                rsi_reason = "RSI healthy 40–70"
                tags.append("rsi_healthy")
            elif rsi > 80:
                timing_score -= 15
                rsi_reason = "RSI overbought >80"
                tags.append("rsi_overbought")
            elif rsi < 30:
                timing_score -= 15
                rsi_reason = "RSI oversold <30"
                tags.append("rsi_oversold")

        if str(market_regime).upper() == "RISK ON":
            timing_score += 5
            tags.append("risk_on")
        elif str(market_regime).upper() == "RISK OFF":
            timing_score -= 10
            tags.append("risk_off")

        timing_score = MAX(0, MIN(100, ROUND(timing_score)))

        timing_action = "WAIT"
        buy_amount = 0
        position_rationale = "Wait — timing does not confirm entry"

        if tier in ["MOMENTUM", "MOONSHOT"] and timing_score >= 80:
            timing_action = "TIMING CONFIRMED"
            position_rationale = "Timing confirms stronger entry conditions"
        elif timing_score >= 70:
            timing_action = "TIMING WATCH"
            position_rationale = "Timing is close but needs stronger confirmation"

        rows.append({"ticker": ticker,"tier": tier,"market_regime": market_regime,"price": price,"gap_pct": gap_pct,"volume_trend": volume_trend,"timing_score": timing_score,"timing_action": timing_action,"buy_amount_usd": buy_amount,"shares_to_buy": 0,"stop_loss": row.get("stop_loss", np.nan),"trim_price": row.get("trim_price", np.nan),"reason_tags": "; ".join(tags),"position_rationale": position_rationale,"gap_reason": gap_reason,"volume_reason": volume_reason,"macd_reason": macd_reason,"rsi_reason": rsi_reason,"data_note": "Uses daily yfinance data, not true live premarket/after-hours data",})

    out = pd.DataFrame(rows).sort_values("timing_score", ascending=FALSE)
    out.to_csv(MARKET_TIMING_PATH, index=FALSE)
    return out

if __name__ == "__main__":
    score_market_timing()
