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
        ws.column_dimensions[col_letter].width = min(max_len + 2, 32)

def style_sheet(ws):
    for cell in ws[1]:
        cell.fill = PatternFill("solid", fgColor="1F4E78")
        cell.font = Font(color="FFFFFF", bold=True)
        cell.alignment = Alignment(horizontal="center")
    autosize(ws)

def highlight_actions(ws, action_header):
    headers = [cell.value for cell in ws[1]]
    if action_header not in headers:
        return

    action_col = headers.index(action_header) + 1

    for row in ws.iter_rows(min_row=2):
        action = row[action_col - 1].value
        if action in ["BUY", "PREMARKET BUY"]:
            fill = PatternFill("solid", fgColor="C6EFCE")
        elif action == "BUY SMALL":
            fill = PatternFill("solid", fgColor="D9EAF7")
        elif action in ["WATCH", "PREMARKET WATCH"]:
            fill = PatternFill("solid", fgColor="FFF2CC")
        elif action == "SELL":
            fill = PatternFill("solid", fgColor="F4CCCC")
        else:
            fill = None

        if fill:
            for cell in row:
                cell.fill = fill

def build_excel_workbook():
    OUTPUT_DIR.mkdir(exist_ok=True)

    files = {
        "DASHBOARD": DATA_DIR / "dashboard.csv",
        "HOLDINGS": DATA_DIR / "holdings.csv",
        "CASH": DATA_DIR / "cash.csv",
        "PERFORMANCE": DATA_DIR / "performance.csv",
        "WEEKLY_REVIEW": DATA_DIR / "weekly_review.csv",
        "SIGNALS_FULL": DATA_DIR / "signals.csv",
        "PREMARKET_FULL": DATA_DIR / "premarket_signals.csv",
        "MARKET_DATA": DATA_DIR / "market_data.csv",
        "TRADE_LOG": DATA_DIR / "trades.csv",
        "MARKET_REGIME": DATA_DIR / "market_regime.csv",
    }

    excel_file = OUTPUT_DIR / "trading_summary.xlsx"

    with pd.ExcelWriter(excel_file, engine="openpyxl") as writer:
        for sheet, path in files.items():
            df = read_csv_safe(path)

            if df.empty:
                df = pd.DataFrame([{"status": "No data available yet"}])

            df.to_excel(writer, sheet_name=sheet, index=False)

        instructions = pd.DataFrame([
            {"Step": 1, "Action": "Open DASHBOARD first. It is the clean action view generated from GitHub."},
            {"Step": 2, "Action": "Review SELL / exit warnings before any new buys."},
            {"Step": 3, "Action": "Check HOLDINGS and CASH before trading."},
            {"Step": 4, "Action": "Use BUY / BUY SMALL as candidates, not automatic trades."},
            {"Step": 5, "Action": "For full sells in trades.csv, use shares=ALL."},
            {"Step": 6, "Action": "Run GitHub workflow, then refresh Excel."},
        ])
        instructions.to_excel(writer, sheet_name="INSTRUCTIONS", index=False)

        wb = writer.book
        for ws in wb.worksheets:
            style_sheet(ws)

            if ws.title == "DASHBOARD":
                highlight_actions(ws, "action")

            if ws.title == "SIGNALS_FULL":
                highlight_actions(ws, "action")

            if ws.title == "PREMARKET_FULL":
                highlight_actions(ws, "premarket_action")

            for row in ws.iter_rows():
                for cell in row:
                    cell.alignment = Alignment(vertical="top", wrap_text=True)

    print(f"Excel workbook created: {excel_file}")
    return excel_file

if __name__ == "__main__":
    build_excel_workbook()
