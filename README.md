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

```bash
git clone https://github.com/nicklc14/trading-engine-v2.git
cd trading-engine-v2
pip install -r requirements.txt
mkdir -p data output
cp data_template/*.csv data/
python scripts/run_all.py
Open:
output/trading_summary.xlsx
Daily Workflow
Open the generated Excel workbook.
Review Dashboard first.
Review SELL / TRIM rows before any buys.
Check add_more for existing holdings.
Check Data Quality.
Check Market Timing.
Check Holdings and Performance Summary.
Make final trading decisions manually.
Log trades in data/trades.csv.
Rerun workflow or wait for scheduled run.
Main Sheets
Dashboard — clean action view.
Holdings — current positions and cash.
Trades — trade log.
Performance Summary — account-level performance.
Weekly Review — weekly closed trade review.
Performance Learning — early learning by tier/reason/action.
Data Quality — stale/missing/unreliable data checks.
Signals Full — full signal detail.
Market Timing — timing confirmation from daily yfinance data.
Market Data — raw market indicators.
Important Scripts
scripts/run_all.py
Runs the full pipeline in order.
scripts/update_market_data.py
Pulls yfinance market data and creates:
data/market_data.csv
data/market_regime.csv
scripts/check_data_quality.py
Checks for:
stale fetches
missing tickers
missing prices
missing ATR
missing volume data
old market candles
scripts/score_signals.py
Scores tickers and applies:
market regime logic
risk controls
max position rules
max moonshot rules
no averaging down
add-more logic
sell/trim logic
scripts/score_market_timing.py
Creates data/market_timing.csv.
This uses daily yfinance data. It is not true live premarket or after-hours data.
scripts/build_dashboard.py
Creates data/dashboard.csv.
scripts/build_excel_workbook.py
Creates output/trading_summary.xlsx.
Key Outputs
data/dashboard.csv
data/signals.csv
data/market_timing.csv
data/data_quality_report.csv
data/holdings.csv
data/performance.csv
output/trading_summary.xlsx
GitHub Actions
Workflow file:
.github/workflows/trading-engine-v2.yml
Current schedule:
cron: '30 20 * * 1-5'
This runs about 30 minutes after US market close during US daylight saving time.
NZ time equivalent:
About 8:30 AM NZST, Tuesday–Saturday.
Adjust may be needed when US daylight saving changes.
You can also run it manually:
Actions → Trading Engine V2 → Run workflow
Risk Controls
The system currently includes:
max open positions
max moonshot positions
no averaging down
add only to winners
weekly loss stop
block new buys when high-priority sells exist
risk-off market regime adjustments
data freshness checks
Important Notes
Market Timing replaced the old premarket naming.
Reason: the current free data source is yfinance daily data. It is useful for timing confirmation, but it should not be treated as reliable live premarket data.
A better real-time or extended-hours source can be added later when the portfolio is larger.
Troubleshooting
If the workbook looks wrong, check:
Data Quality
GitHub Actions logs
data/dashboard.csv
data/signals.csv
data/market_timing.csv
If Excel query columns break after a schema change:
Clear query cache.
Refresh all.
If still broken, delete and re-import the affected query/table.
