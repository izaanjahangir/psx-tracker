"""
Exports the structure of your Portfolio Tracker sheet to template.json:
tabs, formulas, labels, formatting, dropdowns, column widths and charts.
Your data (trades, dividends, daily performance history) is NOT exported.

Run this after you change the sheet's structure, then commit template.json.

Usage:
  .venv/bin/python export_template.py
"""

import json

from config import DIVIDEND_SHEET, PERF_SHEET, PRICES_SHEET, TEMPLATE_FILE, TRADE_SHEET, open_spreadsheet, spreadsheet_id


# Rows (0-based, inclusive start) where typed values are personal data and are dropped.
# Formulas in these rows are kept.
DATA_START_ROW = {
    TRADE_SHEET: 1,          # trades start on row 2
    DIVIDEND_SHEET: 7,   # dividend entries start on row 8
    PERF_SHEET: 1,           # written by update_performance.py
    PRICES_SHEET: 1,         # written by update_performance.py
}

FIELDS = (
    "properties(locale,timeZone),"
    "sheets(properties,merges,conditionalFormats,bandedRanges,charts,basicFilter,"
    "data(rowMetadata(pixelSize),columnMetadata(pixelSize),"
    "rowData(values(userEnteredValue,userEnteredFormat,dataValidation,note))))"
)


def is_formula(cell):
    return "formulaValue" in cell.get("userEnteredValue", {})


def export():
    book = open_spreadsheet(spreadsheet_id())
    meta = book.fetch_sheet_metadata(params={"includeGridData": "true", "fields": FIELDS})

    styles, style_index = [], {}

    def style_id(cell):
        style = {k: cell[k] for k in ("userEnteredFormat", "dataValidation", "note") if k in cell}
        if not style:
            return None
        key = json.dumps(style, sort_keys=True)
        if key not in style_index:
            style_index[key] = len(styles)
            styles.append(style)
        return style_index[key]

    sheets = []
    for sheet in meta["sheets"]:
        props = sheet["properties"]
        title = props["title"]
        data = sheet["data"][0]
        data_start = DATA_START_ROW.get(title)

        values, style_runs = [], []  # values: [row, col, userEnteredValue]
        grid = {}
        for r, row in enumerate(data.get("rowData", [])):
            for c, cell in enumerate(row.get("values", [])):
                if not cell:
                    continue
                if "userEnteredValue" in cell:
                    keep = data_start is None or r < data_start or is_formula(cell)
                    if keep:
                        values.append([r, c, cell["userEnteredValue"]])
                sid = style_id(cell)
                if sid is not None:
                    grid[(r, c)] = sid

        # Compress styles into vertical runs: [col, first_row, last_row, style]
        for c in sorted({c for _, c in grid}):
            rows = sorted(r for r, cc in grid if cc == c)
            start = prev = rows[0]
            for r in rows[1:] + [None]:
                if r is not None and r == prev + 1 and grid[(r, c)] == grid[(start, c)]:
                    prev = r
                    continue
                style_runs.append([c, start, prev, grid[(start, c)]])
                if r is not None:
                    start = prev = r

        sheets.append({
            "properties": {k: props[k] for k in ("sheetId", "title", "index", "gridProperties", "hidden", "tabColorStyle") if k in props},
            "columnWidths": [[i, m["pixelSize"]] for i, m in enumerate(data.get("columnMetadata", [])) if m.get("pixelSize", 100) != 100],
            "rowHeights": [[i, m["pixelSize"]] for i, m in enumerate(data.get("rowMetadata", [])) if m.get("pixelSize", 21) != 21],
            "values": values,
            "styleRuns": style_runs,
            "merges": sheet.get("merges", []),
            "conditionalFormats": sheet.get("conditionalFormats", []),
            "bandedRanges": sheet.get("bandedRanges", []),
            "basicFilter": sheet.get("basicFilter"),
            "charts": sheet.get("charts", []),
        })

    template = {
        "version": 1,
        "spreadsheet": meta["properties"],
        "styles": styles,
        "sheets": sorted(sheets, key=lambda s: s["properties"]["index"]),
    }
    TEMPLATE_FILE.write_text(json.dumps(template, indent=1, ensure_ascii=False) + "\n")
    print(f"Wrote {TEMPLATE_FILE.name}: {len(sheets)} tabs, {len(styles)} styles, "
          f"{sum(len(s['values']) for s in sheets)} cells with formulas/labels.")


if __name__ == "__main__":
    export()
