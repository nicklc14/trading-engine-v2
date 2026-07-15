import pandas as pd
from pathlib import Path

DATA_DIR = Path("data")

REQUIRED_FILES = {"dashboard": DATA_DIR / "dashboard.csv","candidate_review": DATA_DIR / "candidate_review.csv","holdings_view": DATA_DIR / "holdings_view.csv","trades": DATA_DIR / "trades.csv","performance_summary": DATA_DIR / "performance_summary.csv","weekly_review": DATA_DIR / "weekly_review.csv","performance_learning": DATA_DIR / "performance_learning.csv","data_quality_report": DATA_DIR / "data_quality_report.csv","signals": DATA_DIR / "signals.csv","market_timing": DATA_DIR / "market_timing.csv","market_data": DATA_DIR / "market_data.csv","closed_trades_learning": DATA_DIR / "closed_trades_learning.csv",}

REQUIRED_COLUMNS = {"dashboard": [
        "ticker", "action_required", "add_more", "plan_why",
        "buy_usd", "sell_usd", "shares_to_buy", "shares_to_sell",
        "price", "score", "tier", "holding_return_pct",
        "stop_loss", "trim_target", "risk_note", "position_rule",
    ],"candidate_review": [
        "ticker", "source_list", "sector", "tier", "price", "score",
        "trend_score", "momentum_score", "accelerator_score",
        "timing_action", "timing_score", "recommendation", "why",
    ],"weekly_review": [
        "week_start", "closed_trades", "wins", "losses", "win_rate",
        "realized_pnl_usd", "avg_return_pct", "avg_holding_days",
        "best_trade", "worst_trade",
    ],"performance_learning": [
        "group_type", "group_value", "closed_trades", "wins", "losses",
        "win_rate", "realized_pnl_usd", "avg_return_pct", "avg_pnl_usd",
    ],"data_quality_report": [
        "as_of", "ticker", "issue_type", "severity", "issue", "suggested_action",
    ],"signals": [
        "ticker", "tier", "market_regime", "price", "score", "action",
        "stop_loss", "trim_price", "buy_amount_usd", "shares_to_buy",
        "position_rule", "add_more_signal", "decision_reasons", "warnings",
    ],"market_timing": [
        "ticker", "tier", "market_regime", "price", "gap_pct",
        "volume_trend", "timing_score", "timing_action", "data_note",
    ],"market_data": [
        "ticker", "price", "volume", "avg_volume_50", "volume_trend",
        "rsi_14", "atr", "atr_pct", "as_of", "market_data_date", "fetched_at_utc",
    ],"closed_trades_learning": [
        "week_start", "sell_date", "ticker", "tier", "holding_key",
        "first_buy_date", "holding_days", "buy_cost_usd",
        "sell_proceeds_usd", "realized_pnl_usd", "realized_return_pct", "result",
    ],}

NON_EMPTY_FILES = [
    "dashboard",
    "candidate_review",
    "performance_summary",
    "weekly_review",
    "performance_learning",
    "data_quality_report",
    "signals",
    "market_timing",
    "market_data",
]

VALID_DASHBOARD_ACTIONS = {"SELL","TRIM","HOLD","BUY","BUY SMALL","WATCH"}
VALID_TIMING_ACTIONS = {"TIMING CONFIRMED","TIMING WATCH","WAIT",""}
VALID_QUALITY_SEVERITIES = {"OK","LOW","MEDIUM","HIGH"}
VALID_CANDIDATE_RECOMMENDATIONS = {"PROMOTE","KEEP CANDIDATE","REMOVE","DISABLED","NO CANDIDATES",}
VALID_SOURCE_LISTS = {"CANDIDATE"}

def read_csv(name):
    path = REQUIRED_FILES[name]
    if not path.exists():
        raise FileNotFoundError(f"Missing required output file: {path}")
    if path.stat().st_size == 0:
        raise ValueError(f"Output file is empty: {path}")
    return pd.read_csv(path)

def require_columns(name, df):
    missing = [col for col in REQUIRED_COLUMNS.get(name, []) if col not in df.columns]
    if missing:
        raise ValueError(f"{name}.csv missing required columns: {missing}")

def require_non_empty(name, df):
    if name in NON_EMPTY_FILES and df.empty:
        raise ValueError(f"{name}.csv has no rows")

def validate_dashboard(df):
    bad_actions = set(df["action_required"].dropna().astype(str).str.upper()) - VALID_DASHBOARD_ACTIONS
    if bad_actions:
        raise ValueError(f"dashboard.csv has invalid action_required values: {sorted(bad_actions)}")
    if df["ticker"].isna().any():
        raise ValueError("dashboard.csv has blank ticker values")

def validate_market_timing(df):
    bad_actions = set(df["timing_action"].fillna("").astype(str).str.upper()) - VALID_TIMING_ACTIONS
    if bad_actions:
        raise ValueError(f"market_timing.csv has invalid timing_action values: {sorted(bad_actions)}")

def validate_data_quality(df):
    bad_severities = set(df["severity"].dropna().astype(str).str.upper()) - VALID_QUALITY_SEVERITIES
    if bad_severities:
        raise ValueError(f"data_quality_report.csv has invalid severity values: {sorted(bad_severities)}")

def validate_signals(df):
    if df["ticker"].isna().any():
        raise ValueError("signals.csv has blank ticker values")
    if df["score"].isna().any():
        raise ValueError("signals.csv has blank score values")
    if ((df["score"] < 0) | (df["score"] > 100)).any():
        raise ValueError("signals.csv has score values outside 0–100")

def validate_candidate_review(df):
    bad_sources = set(df["source_list"].dropna().astype(str).str.upper()) - VALID_SOURCE_LISTS
    if bad_sources:
        raise ValueError(f"candidate_review.csv has invalid source_list values: {sorted(bad_sources)}")

    bad_recs = set(df["recommendation"].dropna().astype(str).str.upper()) - VALID_CANDIDATE_RECOMMENDATIONS
    if bad_recs:
        raise ValueError(f"candidate_review.csv has invalid recommendations: {sorted(bad_recs)}")

def validate_outputs():
    print("Validating output files...")
    loaded = {}

    for name in REQUIRED_FILES:
        df = read_csv(name)
        require_columns(name, df)
        require_non_empty(name, df)
        loaded[name] = df

    validate_dashboard(loaded["dashboard"])
    validate_candidate_review(loaded["candidate_review"])
    validate_market_timing(loaded["market_timing"])
    validate_data_quality(loaded["data_quality_report"])
    validate_signals(loaded["signals"])

    print("Validation passed.")
    return TRUE

if __name__ == "__main__":
    validate_outputs()
