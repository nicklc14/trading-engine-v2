import time
import pandas as pd
import requests
from pathlib import Path
from datetime import datetime, timezone, timedelta

DATA_DIR = Path("data")

WATCHLIST_PATH = DATA_DIR / "watchlist.csv"
SEC_EVENTS_PATH = DATA_DIR / "sec_events.csv"

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"

HEADERS = {
    "User-Agent": "nicklc-secevents@outlook.com"
}

LOOKBACK_DAYS = 30

HIGH_RISK_FORMS = {"S-1", "S-3", "424B5", "424B3", "424B2"}
MATERIAL_FORMS = {"8-K"}
OWNERSHIP_FORMS = {"3", "4", "5", "SC 13D", "SC 13G"}

def get_cik_map():
    r = requests.get(SEC_TICKERS_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json()

    mapping = {}
    for _, item in data.items():
        ticker = str(item.get("ticker", "")).upper()
        cik = str(item.get("cik_str", "")).zfill(10)
        if ticker and cik:
            mapping[ticker] = cik

    return mapping

def classify_form(form):
    form = str(form).upper()

    if form in HIGH_RISK_FORMS:
        return "DILUTION_RISK", "HIGH", -5, "Recent offering/registration filing risk"

    if form in MATERIAL_FORMS:
        return "MATERIAL_EVENT", "MEDIUM", 0, "Recent 8-K material event filing"

    if form in OWNERSHIP_FORMS:
        return "OWNERSHIP_FILING", "LOW", 0, "Recent insider/ownership filing"

    return "OTHER_FILING", "LOW", 0, f"Recent {form} filing"

def update_sec_events():
    watch = pd.read_csv(WATCHLIST_PATH)
    watch["ticker"] = watch["ticker"].astype(str).str.upper().str.strip()
    watch["enabled"] = watch["enabled"].astype(str).str.upper().isin(["TRUE", "YES", "1", "Y"])
    watch = watch[watch["enabled"]]

    try:
        cik_map = get_cik_map()
    except Exception as e:
        out = pd.DataFrame([{
            "ticker": "",
            "sec_event_flag": "ERROR",
            "sec_event_type": "",
            "sec_event_date": "",
            "sec_form": "",
            "sec_severity": "LOW",
            "sec_score_adjustment": 0,
            "sec_event_note": f"SEC CIK map lookup failed: {e}",
        }])
        out.to_csv(SEC_EVENTS_PATH, index=False)
        return out

    cutoff = datetime.now(timezone.utc).date() - timedelta(days=LOOKBACK_DAYS)
    rows = []

    for ticker in watch["ticker"]:
        cik = cik_map.get(ticker)

        if not cik:
            rows.append({
                "ticker": ticker,
                "sec_event_flag": "NONE",
                "sec_event_type": "",
                "sec_event_date": "",
                "sec_form": "",
                "sec_severity": "NONE",
                "sec_score_adjustment": 0,
                "sec_event_note": "No SEC CIK found",
            })
            continue

        try:
            url = SEC_SUBMISSIONS_URL.format(cik=cik)
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            data = r.json()

            recent = data.get("filings", {}).get("recent", {})
            forms = recent.get("form", [])
            dates = recent.get("filingDate", [])

            ticker_events = []

            for form, filing_date in zip(forms, dates):
                try:
                    d = datetime.strptime(filing_date, "%Y-%m-%d").date()
                except Exception:
                    continue

                if d < cutoff:
                    continue

                event_type, severity, score_adj, note = classify_form(form)

                if event_type != "OTHER_FILING":
                    ticker_events.append({
                        "ticker": ticker,
                        "sec_event_flag": "YES",
                        "sec_event_type": event_type,
                        "sec_event_date": filing_date,
                        "sec_form": form,
                        "sec_severity": severity,
                        "sec_score_adjustment": score_adj,
                        "sec_event_note": note,
                    })

            if ticker_events:
                severity_rank = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "NONE": 0}
                ticker_events = sorted(
                    ticker_events,
                    key=lambda x: (
                        severity_rank.get(x["sec_severity"], 0),
                        abs(x["sec_score_adjustment"]),
                        x["sec_event_date"]
                    ),
                    reverse=True
                )
                rows.append(ticker_events[0])
            else:
                rows.append({
                    "ticker": ticker,
                    "sec_event_flag": "NONE",
                    "sec_event_type": "",
                    "sec_event_date": "",
                    "sec_form": "",
                    "sec_severity": "NONE",
                    "sec_score_adjustment": 0,
                    "sec_event_note": "No major SEC events in lookback window",
                })

        except Exception as e:
            rows.append({
                "ticker": ticker,
                "sec_event_flag": "ERROR",
                "sec_event_type": "",
                "sec_event_date": "",
                "sec_form": "",
                "sec_severity": "LOW",
                "sec_score_adjustment": 0,
                "sec_event_note": f"SEC lookup failed: {e}",
            })

        time.sleep(0.15)

    out = pd.DataFrame(rows)
    out.to_csv(SEC_EVENTS_PATH, index=False)
    return out

if __name__ == "__main__":
    update_sec_events()
