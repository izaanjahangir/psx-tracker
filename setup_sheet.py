"""
Turns a blank Google Sheet into a PSX Portfolio Tracker: every tab, formula,
format, dropdown and chart from template.json, plus 3 sample trades.

Before running:
  1. Create a blank Google Sheet.
  2. Share it with your service account's email as Editor.

Usage:
  .venv/bin/python setup_sheet.py <spreadsheet-id>
  .venv/bin/python setup_sheet.py <spreadsheet-id> --no-samples   # skip the sample trades
"""

import datetime as dt
import json
import sys

from config import TEMPLATE_FILE, TRADE_SHEET, open_spreadsheet

SHEETS_EPOCH = dt.date(1899, 12, 30)

# (days ago, stock, side, quantity, price, commission, sales tax, CDC charges)
SAMPLE_TRADES = [
    (21, "MEBL (Meezan Bank)", "Buy", 10, 540.00, 8.10, 1.22, 0.05),
    (14, "HUBC (The Hub Power Company Limited)", "Buy", 20, 205.00, 6.15, 0.92, 0.10),
    (7, "MEBL (Meezan Bank)", "Sell", 5, 555.00, 4.16, 0.62, 0.03),
]


def last_weekday(days_ago):
    day = dt.date.today() - dt.timedelta(days=days_ago)
    while day.weekday() >= 5:
        day -= dt.timedelta(days=1)
    return day


def grid_range(sheet_id, r0, r1, c0, c1):
    return {"sheetId": sheet_id, "startRowIndex": r0, "endRowIndex": r1,
            "startColumnIndex": c0, "endColumnIndex": c1}


def check_blank(book):
    for ws in book.worksheets():
        if any(any(cell for cell in row) for row in ws.get_all_values()):
            sys.exit(f"The spreadsheet is not blank (tab '{ws.title}' has data). "
                     "Use a new, empty Google Sheet so nothing gets overwritten.")


def build(book, template, with_samples):
    old_sheets = book.worksheets()
    tabs = template["sheets"]
    used_ids = {t["properties"]["sheetId"] for t in tabs}
    if any(ws.id in used_ids for ws in old_sheets):
        sys.exit("The blank sheet has a tab ID that clashes with the template. Create a new blank sheet and try again.")

    # 1. Spreadsheet settings and empty tabs (keeping the template's tab IDs so charts point to the right tabs)
    requests = [{"updateSpreadsheetProperties": {
        "properties": {k: v for k, v in template["spreadsheet"].items() if k in ("locale", "timeZone")},
        "fields": "locale,timeZone"}}]
    for i, ws in enumerate(old_sheets):
        requests.append({"updateSheetProperties": {"properties": {"sheetId": ws.id, "title": f"__old_{i}"}, "fields": "title"}})
    for tab in tabs:
        requests.append({"addSheet": {"properties": tab["properties"]}})
    for ws in old_sheets:
        requests.append({"deleteSheet": {"sheetId": ws.id}})
    book.batch_update({"requests": requests})

    # 2. Layout, formatting and dropdowns
    requests = []
    for tab in tabs:
        sid = tab["properties"]["sheetId"]
        for dim, sizes in (("COLUMNS", tab["columnWidths"]), ("ROWS", tab["rowHeights"])):
            for index, size in sizes:
                requests.append({"updateDimensionProperties": {
                    "range": {"sheetId": sid, "dimension": dim, "startIndex": index, "endIndex": index + 1},
                    "properties": {"pixelSize": size}, "fields": "pixelSize"}})
        for col, r0, r1, style_id in tab["styleRuns"]:
            requests.append({"repeatCell": {
                "range": grid_range(sid, r0, r1 + 1, col, col + 1),
                "cell": template["styles"][style_id],
                "fields": "userEnteredFormat,dataValidation,note"}})
        for merge in tab["merges"]:
            requests.append({"mergeCells": {"range": merge, "mergeType": "MERGE_ALL"}})
        for rule in tab["conditionalFormats"]:
            requests.append({"addConditionalFormatRule": {"rule": rule, "index": 0}})
        for band in tab["bandedRanges"]:
            requests.append({"addBanding": {"bandedRange": {k: v for k, v in band.items() if k != "bandedRangeId"}}})
        if tab["basicFilter"]:
            requests.append({"setBasicFilter": {"filter": tab["basicFilter"]}})
    book.batch_update({"requests": requests})

    # 3. Labels and formulas (after all tabs exist, so cross-tab formulas resolve)
    requests = []
    for tab in tabs:
        sid = tab["properties"]["sheetId"]
        for r, c, value in tab["values"]:
            requests.append({"updateCells": {
                "start": {"sheetId": sid, "rowIndex": r, "columnIndex": c},
                "rows": [{"values": [{"userEnteredValue": value}]}],
                "fields": "userEnteredValue"}})
    book.batch_update({"requests": requests})

    # 4. Charts
    requests = []
    for tab in tabs:
        for chart in tab["charts"]:
            requests.append({"addChart": {"chart": {"spec": chart["spec"], "position": chart["position"]}}})
    if requests:
        book.batch_update({"requests": requests})

    # 5. Sample trades
    if with_samples:
        rows = [[(last_weekday(ago) - SHEETS_EPOCH).days, *rest] for ago, *rest in SAMPLE_TRADES]
        book.worksheet(TRADE_SHEET).update(range_name=f"A2:H{len(rows) + 1}", values=rows, value_input_option="RAW")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        sys.exit(__doc__)
    if not TEMPLATE_FILE.exists():
        sys.exit(f"{TEMPLATE_FILE.name} not found.")

    template = json.loads(TEMPLATE_FILE.read_text())
    book = open_spreadsheet(args[0])
    check_blank(book)

    print(f"Setting up '{book.title}' from {TEMPLATE_FILE.name} ...")
    build(book, template, with_samples="--no-samples" not in sys.argv)

    errors = [(ws.title, cell) for ws in book.worksheets() for row in ws.get_all_values()
              for cell in row if cell.startswith("#") and cell not in ("#", "# of shares")]
    print(f"Done: {len(template['sheets'])} tabs created.")
    if errors:
        print(f"Warning: {len(errors)} cell(s) show errors, e.g. {errors[:3]}")
    print(f"\nOpen it: https://docs.google.com/spreadsheets/d/{args[0]}/edit")
    print("Next: put this spreadsheet's ID in .env as SPREADSHEET_ID, then run ./psx update")


if __name__ == "__main__":
    main()
