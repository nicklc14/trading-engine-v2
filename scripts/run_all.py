from update_market_data import update_market_data
from score_signals import score_signals
from score_premarket_signals import score_premarket_signals
from calculate_holdings import calculate_holdings
from build_excel_workbook import build_excel_workbook

print("Starting Trading Engine V2...")

print("Step 1: Updating market data...")
update_market_data()

print("Step 2: Scoring standard signals...")
score_signals()

print("Step 3: Scoring premarket signals...")
score_premarket_signals()

print("Step 4: Calculating holdings...")
calculate_holdings()

print("Step 5: Building Excel workbook...")
build_excel_workbook()

print("Done.")
