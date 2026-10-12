"""
Refreshes the "Daily Performance" tab of the Portfolio Tracker sheet.

For every trading day in the last DAYS_TO_REFILL days (plus any gap since the
last row), it downloads PSX's daily files and writes:
  A Date, B Portfolio Value, E KSE-100, F KSE-100 %
All other columns on that tab are formulas and update themselves.
KSE-100 closes come from sarmaaya.pk's published history. Any day it doesn't
have yet is filled by rebuilding the change from PSX's index file.
It also writes each traded stock's latest closing price to the
"Latest Prices" tab (used by the Charts tab).

Usage:
  .venv/bin/python update_performance.py            # update the sheet
  .venv/bin/python update_performance.py --dry-run  # only show what would change
  .venv/bin/python update_performance.py <spreadsheet-id> [--dry-run]
      # use this spreadsheet instead of SPREADSHEET_ID from .env
"""

import datetime as dt
import io
import json
import re
import sys
import urllib.error
import urllib.request
import zipfile
from math import prod

import gspread
import xlrd

from config import (DAYS_TO_REFILL, KSE100_HISTORY_URL, PERF_SHEET, PRICES_SHEET, PSX, TRADE_SHEET,
                    open_spreadsheet, spreadsheet_id)

SHEETS_EPOCH = dt.date(1899, 12, 30)  # Google Sheets date serial 0


def fetch(url):
    """Bytes of url, or None if PSX has no file for it (weekend/holiday)."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        return urllib.request.urlopen(req, timeout=30).read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def psx_closes(day):
    """{symbol: (close, previous close)} for every PSX symbol, or None if no trading that day."""
    data = fetch(f"{PSX}/download/mkt_summary/{day.isoformat()}.Z")
    if not data:
        return None
    zf = zipfile.ZipFile(io.BytesIO(data))
    text = zf.read(zf.namelist()[0]).decode("latin-1")
    closes = {}
    for line in text.splitlines():
        p = line.split("|")  # date|symbol|code|name|open|high|low|close|volume|ldcp
        if len(p) > 9 and p[1]:
            closes[p[1]] = (float(p[7]), float(p[9]))
    return closes


def previous_trading_closes(day):
    """Closing prices from the last trading day before `day` (looks back up to 10 days)."""
    for back in range(1, 11):
        earlier = day - dt.timedelta(days=back)
        if earlier.weekday() < 5:
            closes = psx_closes(earlier)
            if closes:
                return closes
    return None


def kse100_change(day, closes, prev_closes):
    """KSE-100 daily change, rebuilt from PSX's free-float constituent file.

    PSX lowers a stock's previous close (LDCP) by the dividend on its ex-date and
    adjusts it for splits/bonus shares, so this matches the total return KSE-100
    (the headline KSE100 index), not the price-only KSE100PR.

    On a split/bonus day the index file already has the new price but still the old
    share count, so the share count is scaled by the same ratio PSX applied to the
    previous close. With that, the rebuild matches PSX's official daily changes.
    """
    data = fetch(f"{PSX}/download/indhist/{day.isoformat()}.xls")
    if not data:
        raise RuntimeError(f"PSX index file missing for {day}")
    sheet = xlrd.open_workbook(file_contents=data).sheet_by_name("KSE-100")
    today_cap = prev_cap = 0.0
    for i in range(1, sheet.nrows):
        row = sheet.row_values(i)  # ISIN, SYMBOL, COMPANY, PRICE, IDX WT %, FF BASED SHARES, ...
        if row[1] not in closes:
            continue
        close, prev = closes[row[1]]
        shares = row[5]
        if prev_closes and row[1] in prev_closes and prev > 0:
            ratio = prev_closes[row[1]][0] / prev
            if ratio > 1.25 or ratio < 0.8:  # split or bonus adjustment, not a dividend
                shares *= ratio
        today_cap += shares * close
        prev_cap += shares * prev
    return today_cap / prev_cap - 1


def kse100_history(days):
    """{date: official KSE-100 close} for the last `days` calendar days, from sarmaaya.pk.
    Returns {} (with a warning) if it can't be reached, so the rebuild is used instead."""
    url = f"{KSE100_HISTORY_URL}?days={days}"
    try:
        data = json.loads(fetch(url) or b"{}")
        return {dt.date.fromisoformat(r["date"][:10]): float(r["price"]) for r in data["response"]}
    except Exception as e:  # network error, changed format, ...
        print(f"Warning: could not read KSE-100 history from {url} ({e}). Using the rebuild instead.\n")
        return {}


def official_kse100():
    """(date, level) of the latest official KSE-100 (headline, total return) shown on the PSX indices page."""
    html = fetch(f"{PSX}/indices").decode("utf-8", "ignore")
    level = re.search(r'item__name">KSE100</div>\s*<div class="topIndices__item__val">([\d,.]+)<', html)
    asof = re.search(r"As of\s+([A-Z][a-z]{2} \d{1,2}, \d{4})", html)
    if not level or not asof:
        return None
    return dt.datetime.strptime(asof.group(1), "%b %d, %Y").date(), float(level.group(1).replace(",", ""))


def holdings_on(day, trades):
    """{ticker: shares held} after all trades dated on or before day."""
    held = {}
    for t_day, stock, side, qty in trades:
        if t_day <= day:
            ticker = stock.strip().split(" ")[0]
            held[ticker] = held.get(ticker, 0) + (-qty if side == "Sell" else qty)
    return {k: v for k, v in held.items() if v}


def to_date(serial):
    return SHEETS_EPOCH + dt.timedelta(days=int(serial))


def to_serial(day):
    return (day - SHEETS_EPOCH).days


def main():
    dry_run = "--dry-run" in sys.argv
    ids = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(ids) > 1:
        sys.exit("Give at most one spreadsheet ID.")
    book = open_spreadsheet(ids[0] if ids else spreadsheet_id())
    print(f"Spreadsheet: {book.title}")
    perf = book.worksheet(PERF_SHEET)

    trades = [
        (to_date(r[0]), r[1], r[2], r[3])
        for r in book.worksheet(TRADE_SHEET).get("A2:D", value_render_option="UNFORMATTED_VALUE")
        if len(r) >= 4 and r[0] != "" and r[3] != ""
    ]
    if not trades:
        sys.exit("Trade List is empty.")

    # Existing rows: {date: [value, level, change]}
    ab = perf.get("A2:B", value_render_option="UNFORMATTED_VALUE")
    ef = perf.get("E2:F", value_render_option="UNFORMATTED_VALUE")
    rows = {}
    for i, r in enumerate(ab):
        if r and r[0] != "":
            e = ef[i] if i < len(ef) else []
            rows[to_date(r[0])] = [r[1] if len(r) > 1 else "", *(e + ["", ""])[:2]]

    today = dt.date.today()
    first_trade = min(t[0] for t in trades)
    start = max(today - dt.timedelta(days=DAYS_TO_REFILL - 1), first_trade)
    if not rows:
        start = first_trade  # empty tab: build the whole history
    elif max(rows) + dt.timedelta(days=1) < start:
        start = max(rows) + dt.timedelta(days=1)  # also fill any gap since the last row

    print(f"Refilling {start} to {today} ({'dry run' if dry_run else 'writing to sheet'})\n")
    print(f"{'Date':<12}{'Portfolio Value':>18}{'KSE-100':>12}{'KSE-100 %':>11}  {'Source':<9} Change vs sheet")
    computed = {}
    last_closes = None
    prev_closes = None
    day = start
    while day <= today:
        closes = psx_closes(day) if day.weekday() < 5 else None
        if closes:
            if prev_closes is None:
                prev_closes = previous_trading_closes(day)
            last_closes = (day, closes)
            held = holdings_on(day, trades)
            missing = [t for t in held if t not in closes]
            if missing:
                sys.exit(f"No PSX closing price on {day} for: {', '.join(missing)}")
            value = round(sum(q * closes[t][0] for t, q in held.items()), 2)
            change = kse100_change(day, closes, prev_closes)
            computed[day] = [value, change]
            prev_closes = closes
        day += dt.timedelta(days=1)

    if not computed:
        print("No trading days in this period.")
        return

    days = sorted(computed)
    history = kse100_history((today - start).days + 15)
    set_kse100_levels(computed, days, history, rows, start)

    for d in days:
        value, lvl, change, source, rebuilt = computed[d]
        old = rows.get(d)
        if not old or not isinstance(old[0], (int, float)):
            diff = "new row"
        else:
            diff = "unchanged" if abs(old[0] - value) < 0.01 else f"value was {old[0]:,.2f}"
        if source == "sarmaaya" and abs(change - rebuilt) > 0.0005:
            diff += f"  (rebuild says {rebuilt:+.2%}, please check)"
        print(f"{d.isoformat():<12}{value:>18,.2f}{lvl:>12,.2f}{change:>10.2%}  {source:<9} {diff}")
        computed[d] = [value, lvl, change]

    official = official_kse100()
    if official and official[0] == days[-1]:
        print(f"\nCheck: PSX official KSE-100 on {official[0]} = {official[1]:,.2f}, "
              f"sheet = {computed[days[-1]][1]:,.2f}")

    if dry_run:
        print("\nDry run: nothing written.")
        return

    rows.update(computed)
    ordered = sorted(rows)
    perf.update(range_name=f"A2:B{len(ordered) + 1}",
                values=[[to_serial(d), rows[d][0]] for d in ordered], value_input_option="RAW")
    perf.update(range_name=f"E2:F{len(ordered) + 1}",
                values=[[rows[d][1], rows[d][2]] for d in ordered], value_input_option="RAW")
    print(f"\nUpdated {len(days)} trading day(s) in '{PERF_SHEET}'.")
    write_latest_prices(book, trades, *last_closes)


def set_kse100_levels(computed, days, history, rows, start):
    """Turn computed[d] = [value, rebuilt change] into [value, level, change, source, rebuilt change].

    Uses the published close where available; otherwise continues from the previous
    day's level with the rebuilt change."""
    # Level on the trading day before the window: published history first, then the sheet
    earlier = [d for d in history if d < start]
    sheet_before = [d for d in rows if d < start and isinstance(rows[d][1], (int, float))]
    level = history[max(earlier)] if earlier else (rows[max(sheet_before)][1] if sheet_before else None)

    if level is None and not any(d in history for d in days):
        # Brand-new sheet and no published history: work backward from PSX's official close
        official = official_kse100()
        if not official or official[0] != days[-1]:
            sys.exit("Could not anchor the KSE-100 level: no published history and the PSX "
                     "indices page is not showing the last trading day.")
        level = official[1]
        for d in reversed(days):
            value, rebuilt = computed[d]
            computed[d] = [value, round(level, 2), rebuilt, "rebuilt", rebuilt]
            level /= 1 + rebuilt
        return

    for d in days:
        value, rebuilt = computed[d]
        if d in history:
            new_level = history[d]
            change = new_level / level - 1 if level else rebuilt
            source = "sarmaaya"
        else:
            if level is None:  # first day missing from history: anchor on the next published close
                nxt = min(x for x in days if x in history and x > d)
                level = history[nxt] / prod(1 + computed[x][1] for x in days if d < x <= nxt) / (1 + rebuilt)
            new_level, change, source = level * (1 + rebuilt), rebuilt, "rebuilt"
        computed[d] = [value, round(new_level, 2), change, source, rebuilt]
        level = new_level


def write_latest_prices(book, trades, day, closes):
    """Latest closing price of every stock in the Trade List, for the Charts tab."""
    tickers = sorted({stock.strip().split(" ")[0] for _, stock, _, _ in trades})
    rows = [[t, closes[t][0], to_serial(day)] for t in tickers if t in closes]
    try:
        ws = book.worksheet(PRICES_SHEET)
    except gspread.WorksheetNotFound:
        ws = book.add_worksheet(PRICES_SHEET, rows=200, cols=3)
    ws.batch_clear(["A2:C"])
    ws.update(range_name="A1:C1", values=[["Ticker", "Latest Close", "As of"]])
    if rows:
        ws.update(range_name=f"A2:C{len(rows) + 1}", values=rows, value_input_option="RAW")
    print(f"Wrote latest closing prices of {len(rows)} stock(s) to '{PRICES_SHEET}' (as of {day}).")


if __name__ == "__main__":
    main()
