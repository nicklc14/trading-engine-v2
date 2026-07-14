import pandas as pd
from pathlib import Path
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.utils import get_column_letter

DATA_DIR = Path("data")
OUTPUT_DIR = Path("output")

def read_csv_safe(path):
    try:
        if path.exists() and path.stat().st_size > 0:
            return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        pass
    return pd.DataFrame()

def autosize(ws):
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            value = "" if cell.value is None else str(cell.value)
            max_len = max(max_len, len(value))
        ws.column_dimensions[col_letter].width = min(max_len + 2, 28)

def style_sheet(ws):
    for cell in ws[1]:
        cell.fill = PatternFill("solid", fgColor="1F4E78")
        cell.font = Font(color="FFFFFF", bold=True)
        cell.alignment = Alignment(horizontal="center")
    autosize(ws)

def build_excel_workbook():
    OUTPUT_DIR.mkdir(exist_ok=True)

    files = {
        "PREMARKET_PLAYS": DATA_DIR / "premarket_signals.csv",
        "BUY_NOW": DATA_DIR / "signals.csv",
        "HOLDINGS": DATA_DIR / "holdings.csv",
        "CASH": DATA_DIR / "cash.csv",
        "DEPOSITS": DATA_DIR / "deposits.csv",
        "MARKET_DATA": DATA_DIR / "market_data.csv",
        "TRADE_LOG": DATA_DIR / "trades.csv",
        "MARKET_REGIME": DATA_DIR / "market_regime.csv",
    }

    excel_file = OUTPUT_DIR / "trading_summary.xlsx"

    with pd.ExcelWriter(excel_file, engine="openpyxl") as writer:
        for sheet, path in files.items():
            df = read_csv_safe(path)

            if sheet == "PREMARKET_PLAYS" and not df.empty:
                df = df[df["premarket_action"].isin(["PREMARKET BUY", "PREMARKET WATCH"])]

            if sheet == "BUY_NOW" and not df.empty:
                df = df[df["action"].isin(["BUY", "BUY SMALL", "WATCH"])]

            if df.empty:
                df = pd.DataFrame([{"status": "No data available yet"}])

            df.to_excel(writer, sheet_name=sheet, index=False)

        instructions = pd.DataFrame([
            {"Step": 1, "Action": "Check CASH first to see available buying power."},
            {"Step": 2, "Action": "Open PREMARKET_PLAYS during NZ evening US premarket window."},
            {"Step": 3, "Action": "Focus only on PREMARKET BUY first."},
            {"Step": 4, "Action": "Check gap_pct, volume_trend, score, stop_loss and trim_price."},
            {"Step": 5, "Action": "Position size is buy_amount_usd. Shares = shares_to_buy."},
            {"Step": 6, "Action": "Set stop loss immediately."},
            {"Step": 7, "Action": "Use trim_price as first profit-taking target."},
            {"Step": 8, "Action": "Log deposits in data/deposits.csv."},
            {"Step": 9, "Action": "Log buys/sells only in data/trades.csv."},
        ])
        instructions.to_excel(writer, sheet_name="INSTRUCTIONS", index=False)

        wb = writer.book
        for ws in wb.worksheets:
            style_sheet(ws)

            if ws.title == "PREMARKET_PLAYS":
                headers = [cell.value for cell in ws[1]]
                if "premarket_action" in headers:
                    action_col = headers.index("premarket_action") + 1
                    for row in ws.iter_rows(min_row=2):
                        action = row[action_col - 1].value
                        if action == "PREMARKET BUY":
                            for cell in row:
                                cell.fill = PatternFill("solid", fgColor="C6EFCE")
                        elif action == "PREMARKET WATCH":
                            for cell in row:
                                cell.fill = PatternFill("solid", fgColor="FFF2CC")

    print(f"Excel workbook created: {excel_file}")
    return excel_file

if __name__ == "__main__":
    build_excel_workbook()
