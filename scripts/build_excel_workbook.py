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

        ws.column_dimensions[col_letter].width = min(max_len + 2, 35)


def style_sheet(ws):
    for cell in ws[1]:
        cell.fill = PatternFill("solid", fgColor="1F4E78")
        cell.font = Font(color="FFFFFF", bold=True)
        cell.alignment = Alignment(horizontal="center")

    for row in ws.iter_rows():
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)

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
            {
                "Step": 1,
                "Action": "Run GitHub Action or confirm latest scheduled run completed."
            },
            {
                "Step": 2,
                "Action": "Open Dashboard / BUY_NOW and review BUY and BUY SMALL candidates first."
            },
            {
                "Step": 3,
                "Action": "Check decision_reasons and warnings before placing any trade."
            },
            {
                "Step": 4,
                "Action": "Confirm cash_available_usd in CASH before trading."
            },
            {
                "Step": 5,
                "Action": "Use buy_amount_usd and shares_to_buy as suggested sizing only."
            },
            {
                "Step": 6,
                "Action": "Set stop_loss immediately after entry."
            },
            {
                "Step": 7,
                "Action": "Use trim_price as first profit-taking reference."
            },
            {
                "Step": 8,
                "Action": "Log all buys/sells in data/trades.csv."
            },
            {
                "Step": 9,
                "Action": "Log deposits only in data/deposits.csv."
            },
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

            if ws.title == "BUY_NOW":
                headers = [cell.value for cell in ws[1]]

                action_col = headers.index("action") + 1 if "action" in headers else None
                warnings_col = headers.index("warnings") + 1 if "warnings" in headers else None

                for row in ws.iter_rows(min_row=2):
                    action = row[action_col - 1].value if action_col else None
                    warnings = row[warnings_col - 1].value if warnings_col else ""

                    if action == "BUY":
                        for cell in row:
                            cell.fill = PatternFill("solid", fgColor="C6EFCE")

                    elif action == "BUY SMALL":
                        for cell in row:
                            cell.fill = PatternFill("solid", fgColor="FFF2CC")

                    elif action == "WATCH":
                        for cell in row:
                            cell.fill = PatternFill("solid", fgColor="D9EAF7")

                    if warnings:
                        for cell in row:
                            cell.fill = PatternFill("solid", fgColor="F4CCCC")

    print(f"Excel workbook created: {excel_file}")
    return excel_file


if __name__ == "__main__":
    build_excel_workbook()
