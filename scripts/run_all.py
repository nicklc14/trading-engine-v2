from normalize_trades import normalize_trades
from update_market_data import update_market_data
from update_sec_events import update_sec_events
from check_data_quality import check_data_quality
from calculate_cash import calculate_cash
from calculate_holdings import calculate_holdings
from calculate_performance import calculate_performance
from score_signals import score_signals
from score_market_timing import score_market_timing
from score_candidates import score_candidates
from build_weekly_review import build_weekly_review
from build_dashboard import build_dashboard
from build_holdings_view import build_holdings_view
from build_performance_summary import build_performance_summary
from build_excel_workbook import build_excel_workbook
from validate_outputs import validate_outputs

print("Starting Trading Engine V2...")

print("Step 0: Normalizing trades...")
normalize_trades()

print("Step 1: Updating market data...")
update_market_data()

print("Step 1b: Updating SEC events...")
update_sec_events()

print("Step 1c: Checking data quality...")
check_data_quality()

print("Step 2: Calculating cash...")
calculate_cash()

print("Step 3: Calculating holdings...")
calculate_holdings()

print("Step 4: Calculating performance...")
calculate_performance()

print("Step 5: Scoring standard signals...")
score_signals()

print("Step 6: Scoring market timing...")
score_market_timing()

print("Step 6b: Scoring candidate watchlist...")
score_candidates()

print("Step 7: Building weekly review...")
build_weekly_review()

print("Step 8: Building dashboard output...")
build_dashboard()

print("Step 9: Building holdings view...")
build_holdings_view()

print("Step 10: Building performance summary...")
build_performance_summary()

print("Step 11: Building Excel workbook...")
build_excel_workbook()

print("Step 12: Validating outputs...")
validate_outputs()

print("Done.")
