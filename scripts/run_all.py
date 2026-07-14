from update_market_data import update_market_data
from calculate_cash import calculate_cash
from calculate_holdings import calculate_holdings
from score_signals import score_signals
from score_premarket_signals import score_premarket_signals
from build_excel_workbook import build_excel_workbook

print("Starting Trading Engine V2...")

print("Step 1: Updating market data...")
update_market_data()

print("Step 2: Calculating cash...")
calculate_cash()

print("Step 3: Calculating holdings...")
calculate_holdings()

print("Step 4: Scoring standard signals...")
score_signals()

print("Step 5: Scoring premarket signals...")
score_premarket_signals()

print("Step 6: Building Excel workbook...")
build_excel_workbook()

print("Done.")
