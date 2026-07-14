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
        gap_pct = row.get("gap_pct", np.nan)
        volume_trend = row.get("volume_trend", np.nan)
        tier = row.get("tier", "QUALITY")
        price = row.get("price", np.nan)

        score = 50

        if pd.notna(gap_pct):
            if gap_pct > 0.10:
                score += 35
            elif gap_pct > 0.05:
                score += 25
            elif gap_pct > 0.03:
                score += 15
            elif gap_pct < -0.03:
                score -= 30

        if pd.notna(volume_trend) and volume_trend >= 1.5:
            score += 20

        action = "SKIP"
        if tier == "MOMENTUM" and score >= 75 and pd.notna(gap_pct) and gap_pct > 0.03:
            action = "PREMARKET BUY"
        elif tier == "MOMENTUM" and score >= 70:
            action = "PREMARKET WATCH"

        buy_amount = 0
        if action == "PREMARKET BUY":
            buy_amount = 20 if score >= 85 else 12

        shares = buy_amount / price if buy_amount > 0 and pd.notna(price) and price > 0 else 0

        rows.append({
            "ticker": row["ticker"],
            "tier": tier,
            "price": price,
            "gap_pct": gap_pct,
            "volume_trend": volume_trend,
            "premarket_score": score,
            "premarket_action": action,
            "buy_amount_usd": buy_amount,
            "shares_to_buy": shares,
            "stop_loss": row.get("stop_loss", np.nan),
            "trim_price": row.get("trim_price", np.nan)
        })

    out = pd.DataFrame(rows).sort_values("premarket_score", ascending=False)
    out.to_csv(PREMARKET_PATH, index=False)
    return out

if __name__ == "__main__":
    score_premarket_signals()
