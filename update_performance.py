"""
Refreshes the "Daily Performance" tab of the Portfolio Tracker sheet.

For every trading day in the last DAYS_TO_REFILL days (plus any gap since the
last row), it downloads PSX's daily files and writes:
  A Date, B Portfolio Value, E KSE-100 (price index), F KSE-100 %
All other columns on that tab are formulas and update themselves.

Usage:
  .venv/bin/python update_performance.py            # update the sheet
  .venv/bin/python update_performance.py --dry-run  # only show what would change
  .venv/bin/python update_performance.py <spreadsheet-id> [--dry-run]
      # use this spreadsheet instead of SPREADSHEET_ID from .env
"""

import datetime as dt
import io
import re
import sys
import urllib.error
import urllib.request
import zipfile

import xlrd

from config import DAYS_TO_REFILL, PERF_SHEET, PSX, TRADE_SHEET, open_spreadsheet, spreadsheet_id

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


def kse100_change(day, closes):
    """KSE-100 price index daily change, rebuilt from PSX's free-float constituent file."""
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
        today_cap += row[5] * close
        prev_cap += row[5] * prev
    return today_cap / prev_cap - 1


def official_kse100pr():
    """(date, level) of the latest official KSE100PR close shown on the PSX indices page."""
    html = fetch(f"{PSX}/indices").decode("utf-8", "ignore")
    level = re.search(r'item__name">KSE100PR</div>\s*<div class="topIndices__item__val">([\d,.]+)<', html)
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

    # KSE-100 level continues from the last row before the refill window
    before = [d for d in rows if d < start and rows[d][1] != ""]
    level = rows[max(before)][1] if before else None

    print(f"Refilling {start} to {today} ({'dry run' if dry_run else 'writing to sheet'})\n")
    print(f"{'Date':<12}{'Portfolio Value':>18}{'KSE-100':>12}{'KSE-100 %':>11}   Change vs sheet")
    computed = {}
    day = start
    while day <= today:
        closes = psx_closes(day) if day.weekday() < 5 else None
        if closes:
            held = holdings_on(day, trades)
            missing = [t for t in held if t not in closes]
            if missing:
                sys.exit(f"No PSX closing price on {day} for: {', '.join(missing)}")
            value = round(sum(q * closes[t][0] for t, q in held.items()), 2)
            change = kse100_change(day, closes)
            computed[day] = [value, change]
        day += dt.timedelta(days=1)

    if not computed:
        print("No trading days in this period.")
        return

    # Index level: chain forward from the previous row, or back from PSX's official close
    days = sorted(computed)
    if level is None:
        official = official_kse100pr()
        if not official or official[0] != days[-1]:
            sys.exit("Could not anchor the KSE-100 level: the PSX indices page is not showing the last trading day.")
        level = official[1]
        for d in reversed(days):
            computed[d].insert(1, round(level, 2))
            level /= 1 + computed[d][2]
    else:
        level = rows[max(before)][1]
        for d in days:
            level *= 1 + computed[d][1]
            computed[d].insert(1, round(level, 2))

    for d in days:
        value, lvl, change = computed[d]
        old = rows.get(d)
        if not old or not isinstance(old[0], (int, float)):
            diff = "new row"
        else:
            diff = "unchanged" if abs(old[0] - value) < 0.01 else f"value was {old[0]:,.2f}"
        print(f"{d.isoformat():<12}{value:>18,.2f}{lvl:>12,.2f}{change:>10.2%}   {diff}")

    official = official_kse100pr()
    if official and official[0] == days[-1]:
        print(f"\nCheck: PSX official KSE-100 price index on {official[0]} = {official[1]:,.2f}, "
              f"rebuilt = {computed[days[-1]][1]:,.2f}")

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


if __name__ == "__main__":
    main()
