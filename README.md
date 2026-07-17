# Trading Engine V2

Aggressive momentum and moonshot trading engine for NZ-based review of US stocks.

> Not financial advice. Use as a decision-support tool only.

## Purpose

This repo supports a high-risk, high-return trading plan.

Strategy:
- Deposit about $100 NZD per fortnight.
- Convert to USD through Sharesies.
- Trade mainly US momentum and moonshot stocks.
- Use some quality stocks where appropriate.
- Aim for high short-term returns.
- Accept higher risk and possible losses.
- Review results after 6 months and 1 year.

Excel is the viewer. Core trading logic should stay in Python/GitHub.

## Quick Start

    git clone https://github.com/nicklc14/trading-engine-v2.git
    cd trading-engine-v2
    pip install -r requirements.txt
    mkdir -p data output
    cp data_template/*.csv data/
    python scripts/run_all.py

Open:

    output/trading_summary.xlsx

## Manual Input Files

- `data/config.csv` - strategy/risk settings.
- `data/trades.csv` - trade log.
- `data/dashboard_watchlist.csv` - active Dashboard watchlist.
- `data/candidate_pool.csv` - inactive candidate pool.
- `data/deposits.csv` - deposits/exchanges, if used.

## Dashboard Watchlist vs Candidate Pool

### `data/dashboard_watchlist.csv`

Active scoring pool: held tickers plus top active non-held candidates.

### `data/candidate_pool.csv`

Inactive candidate pool: monitored names not currently active enough for Dashboard.

## Daily Workflow

1. Open the generated Excel workbook.
2. Review `Dashboard` first.
3. Review `SELL` / `TRIM` rows before any buys.
4. Review held positions and replacement-review notes.
5. Review active watchlist rows.
6. Check `Data Quality`.
7. Check `Market Timing`.
8. Check `Holdings` and `Performance Summary`.
9. Make final trading decisions manually.
10. Log trades in `data/trades.csv`.
11. Rerun workflow or wait for scheduled run.

## Main Sheets

- `Dashboard` - clean daily action view from `data/dashboard.csv`.
- `Candidate Review` - review view of `data/candidate_pool.csv`.
- `Holdings` - current positions and cash.
- `Trades` - trade log.
- `Performance Summary` - account-level performance.
- `Weekly Review` - weekly closed trade review.
- `Performance Learning` - early learning by tier/reason/action.
- `Data Quality` - stale/missing/unreliable data checks.
- `Signals Full` - full signal detail.
- `Market Timing` - timing confirmation from daily yfinance data.
- `Market Data` - raw market indicators.

## Important Scripts

### `scripts/run_all.py`

Runs the full pipeline in order.

### `scripts/update_market_data.py`

Pulls yfinance market data for `data/dashboard_watchlist.csv` and `data/candidate_pool.csv`.

Creates:
- `data/market_data.csv`
- `data/market_regime.csv`

### `scripts/score_candidates.py`

Manages movement between `data/dashboard_watchlist.csv` and `data/candidate_pool.csv`.

Rules:
- held tickers stay active
- top non-held candidates stay in Dashboard watchlist
- other names stay in candidate pool
- keeps at least one close MOMENTUM name if appropriate

Creates:
- `data/candidate_review.csv`

### `scripts/score_signals.py`

Scores active Dashboard watchlist tickers and applies risk, buy, sell, trim, add-more, and moonshot hold-flex rules.

Creates:
- `data/signals.csv`

### `scripts/score_market_timing.py`

Creates:
- `data/market_timing.csv`

Uses daily yfinance data, not live premarket or after-hours data.

### `scripts/build_dashboard.py`

Creates:
- `data/dashboard.csv`

Adds replacement-review notes where a weak held ticker may be worth replacing with a stronger active candidate.

### `scripts/build_excel_workbook.py`

Creates:
- `output/trading_summary.xlsx`

## Key Outputs

- `data/dashboard.csv`
- `data/candidate_review.csv`
- `data/signals.csv`
- `data/market_timing.csv`
- `data/data_quality_report.csv`
- `data/holdings.csv`
- `data/performance.csv`
- `output/trading_summary.xlsx`

## GitHub Actions

Workflow file:

    .github/workflows/trading-engine-v2.yml

Current schedule:

    cron: '30 20 * * 1-5'

Runs about 30 minutes after US market close during US daylight saving time.

NZ time equivalent:
- About `8:30 AM NZST`, Tuesday-Saturday.
- Adjustment may be needed when US daylight saving changes.

Manual run:

    Actions -> Trading Engine V2 -> Run workflow

## Risk Controls

- max open positions
- max moonshot positions
- no averaging down
- add only to winners
- weekly loss stop
- block new buys when high-priority sells exist
- risk-off market regime adjustments
- data freshness checks
- replacement-review flags, but not automatic replacement sells

## Important Notes

`Market Timing` uses yfinance daily data.

It is useful for timing confirmation, but should not be treated as reliable live premarket or after-hours data.

## Troubleshooting

If the workbook looks wrong, check:

1. `Data Quality`
2. GitHub Actions logs
3. `data/dashboard.csv`
4. `data/signals.csv`
5. `data/market_timing.csv`
6. `data/dashboard_watchlist.csv`
7. `data/candidate_pool.csv`

If Excel query columns break after a schema change:

1. Clear query cache.
2. Refresh all.
3. If still broken, delete and re-import the affected query/table.
