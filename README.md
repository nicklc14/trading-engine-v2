# Trading Engine V2 - Premarket Momentum Edition

Trading signal engine for NZ after-hours monitoring of US momentum and quality stocks.

> Not financial advice. Use as a decision-support tool only.

## Quick Start

```
git clone https://github.com/nicklc14/trading-engine-v2.git
cd trading-engine-v2
pip install -r requirements.txt
mkdir -p data output
cp data_template/*.csv data/
python scripts/run_all.py
```

Open:

```text
output/trading_summary.xlsx
```

## Main Tabs

- `PREMARKET_PLAYS` — premarket buy/watch candidates
- `BUY_NOW` — standard signal rankings
- `HOLDINGS` — current holdings from trade log
- `MARKET_DATA` — raw Yahoo Finance indicators
- `TRADE_LOG` — trade log template
- `MARKET_REGIME` — risk-on / risk-off check
- `INSTRUCTIONS` — usage guide

## Trading Flow

1. Open `PREMARKET_PLAYS`.
2. Filter for `PREMARKET BUY`.
3. Review:
   - `gap_pct`
   - `volume_trend`
   - `premarket_score`
   - `stop_loss`
   - `trim_price`
4. Use `buy_amount_usd` as suggested position size.
5. Log trades in `data/trades.csv`.

## GitHub Actions

The workflow runs weekdays at 6am UTC and updates:

- `data/*.csv`
- `output/trading_summary.xlsx`

You can also run it manually from:

`Actions → Trading Engine V2 → Run workflow`
