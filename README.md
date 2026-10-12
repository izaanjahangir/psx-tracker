# PSX Tracker

Tracks how a Pakistan Stock Exchange (PSX) portfolio performs **day by day against the KSE-100 index**, inside a Google Sheet.

Brokers usually show only today's change. This script builds a history: one row per trading day with your portfolio's value, your daily return, the KSE-100's daily return, and running totals since you started. Over time you can see whether your stock picks beat the market.

It has two parts:

- **`./psx setup`** builds the whole tracker (every tab, formula, format, dropdown and chart) in a blank Google Sheet, with 3 sample trades to start from.
- **`./psx update`** keeps the Daily Performance tab up to date.

Each update run:

1. Reads your trades from the **Trade List** tab of your Google Sheet.
2. Downloads PSX's free end-of-day files for each trading day.
3. Prices your holdings at each day's closing prices and works out the KSE-100's daily change.
4. Reads KSE-100's published daily closes from sarmaaya.pk (rebuilding any missing day from PSX's files).
5. Writes the results to the **Daily Performance** tab, and each stock's latest closing price to the **Latest Prices** tab. Formulas calculate everything else, including the charts on the **Charts** tab.

Run it whenever you like. Each run re-prices the last `DAYS_TO_REFILL` days (30 by default) using your current Trade List, so trades you enter a few days late are picked up automatically. It also fills any gap since the last row.

---

## Contents

- [Requirements](#requirements)
- [One-time setup](#one-time-setup)
- [Create your own tracker sheet](#create-your-own-tracker-sheet)
- [Configuration (.env)](#configuration-env)
- [Running the script](#running-the-script)
- [Spreadsheet layout](#spreadsheet-layout)
- [Charts tab](#charts-tab)
- [Changing the sheet's structure](#changing-the-sheets-structure)
- [How the numbers are calculated](#how-the-numbers-are-calculated)
- [Data sources](#data-sources)
- [Troubleshooting](#troubleshooting)
- [Security](#security)
- [Limitations](#limitations)

---

## Requirements

- macOS, Linux or Windows with **Python 3.10+**
- A Google account that owns (or can edit) the spreadsheet
- A free **Google Cloud service account**: a robot account that can edit only the spreadsheets you share with it (setup below)

---

## One-time setup

### 1. Create a Google service account

The script signs in to Google as a robot account. That account can only open spreadsheets you explicitly share with it. It has no access to your Gmail, your Drive, or your other files.

1. Go to <https://console.cloud.google.com> and create a project (for example `psx-sheet-bot`). Leave **Parent resource** as *No organization*.
2. Go to **APIs & Services → Library**, search for **Google Sheets API**, and click **Enable**.
3. Go to **IAM & Admin → Service Accounts → Create service account**. Give it a name (for example `sheet-editor`) and skip the optional role steps.
4. Open the service account, then **Keys → Add key → Create new key → JSON**. A `.json` file downloads.
5. Move that file into this project folder and name it `service-account.json`. It's covered by `.gitignore`, so it won't be committed.
6. Copy the service account's email (it looks like `sheet-editor@psx-sheet-bot.iam.gserviceaccount.com`).
7. In your spreadsheet, click **Share**, paste that email, choose **Editor**, and untick *Notify people*.

### 2. Create your settings file

```bash
cp .env.example .env
```

Open `.env` and set at least `SPREADSHEET_ID` (see [Configuration](#configuration-env)).

### 3. Install the Python dependencies

From this folder:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

On Windows use `.venv\Scripts\pip` and `.venv\Scripts\python` instead of `.venv/bin/...`, and run the Python script directly (the `psx` shortcut is for macOS/Linux).

### 4. Create your tracker sheet

Skip this if you already have a tracker sheet. See [Create your own tracker sheet](#create-your-own-tracker-sheet).

### 5. Check that everything works

```bash
./psx dry-run
```

You should see a table of trading days and a line comparing the rebuilt KSE-100 with PSX's official figure. A dry run never writes to the sheet.

---

## Create your own tracker sheet

`template.json` holds the structure of the tracker: all tabs, labels, formulas, number formats, colours, dropdowns, column widths and charts. It holds **no personal data**. `setup_sheet.py` rebuilds that structure in a blank Google Sheet.

1. Create a blank Google Sheet (<https://sheets.new>) and give it a name.
2. Click **Share**, add your service account's email as **Editor**, and untick *Notify people*.
3. Copy the sheet's ID from its URL: `docs.google.com/spreadsheets/d/`**`<THIS PART>`**`/edit`.
4. Run:

   ```bash
   ./psx setup <spreadsheet-id>
   ```

   Add `--no-samples` if you don't want the sample trades.
5. Put the same ID in `.env` as `SPREADSHEET_ID`.
6. Replace the sample trades in **Trade List** with your own (or keep them while you try things out). Then run:

   ```bash
   ./psx update
   ```

   On an empty Daily Performance tab, the first run builds the history all the way back to your first trade.

**What you get:**

| Tab | Purpose |
|---|---|
| Trade List | Where you enter every buy and sell. Gross, charges, net amount, cost basis and realized P/L are calculated for you. |
| Dividend summary | Enter dividends (ex-date, stock, dividend per share, tax rate, status). Shares held, amounts and yield are calculated. |
| Dashboard | Totals and charts, for all stocks or one stock (pick it in cell B1) |
| Dashboard_Data | Hidden helper tab for the Dashboard |
| Charts | Four performance charts with their key numbers (see [Charts tab](#charts-tab)) |
| Charts_Data | Hidden helper tab for the drawdown chart |
| Daily Summary | Trades, investment, charges and realized P/L per day |
| Portfolio Summary | Holdings per stock, weights, realized P/L, and average, lowest and highest buy prices (with and without charges) |
| Daily Performance | Daily and cumulative return vs KSE-100, filled by `./psx update` |
| Latest Prices | Latest closing price of every stock you have traded, filled by `./psx update` |

**Sample trades** (dated in the last few weeks so `./psx update` has something to price):

| Stock | Side | Qty | Price |
|---|---|---|---|
| MEBL (Meezan Bank) | Buy | 10 | 540.00 |
| HUBC (The Hub Power Company Limited) | Buy | 20 | 205.00 |
| MEBL (Meezan Bank) | Sell | 5 | 555.00 |

The setup script refuses to run on a sheet that already has data, so it can never overwrite a real tracker.

When entering trades, type column **B** as `TICKER (Company name)`. The ticker must match the PSX symbol, because `./psx update` uses it to look up closing prices.

---

## Configuration (.env)

All settings that differ between people live in `.env`. That file isn't committed; `.env.example` is the committed template.

| Setting | Required | Default | Description |
|---|---|---|---|
| `SPREADSHEET_ID` | Yes (for `update`, unless you give an ID) | – | The ID in your sheet's URL: `docs.google.com/spreadsheets/d/`**`<SPREADSHEET_ID>`**`/edit` |
| `GOOGLE_KEY_FILE` | No | `service-account.json` | Path to the service account key, relative to this folder |
| `TRADE_SHEET` | No | `Trade List` | Name of the tab holding your trades |
| `PERF_SHEET` | No | `Daily Performance` | Name of the daily performance tab the script writes to |
| `PRICES_SHEET` | No | `Latest Prices` | Name of the tab the script writes latest closing prices to (created if missing) |
| `DAYS_TO_REFILL` | No | `30` | How many days back to re-price on every run. Increase it if you often enter trades more than 30 days late. Set it high (e.g. `400`) to rebuild your whole history. |
| `PSX_BASE_URL` | No | `https://dps.psx.com.pk` | PSX Data Portal address. Only change it if PSX moves the portal. |
| `KSE100_HISTORY_URL` | No | `https://beta-restapi.sarmaaya.pk/api/indices/price-history/KSE100` | Published daily KSE-100 closes. Only change it if the address moves. |

---

## Running the script

Use the `psx` shortcut from this folder:

```bash
./psx update     # refresh the Daily Performance tab
./psx dry-run    # show what would change, without writing to the sheet
./psx update <id>   # same, for another sheet instead of the one in .env
./psx setup <id> # build the tracker in a blank Google Sheet
./psx export-template  # save your sheet's structure to template.json
./psx            # list the commands
```

It works from any folder if you give its path, e.g. `~/Desktop/psx-tracker/psx update`.

`update` and `dry-run` use `SPREADSHEET_ID` from `.env`. To work on a different sheet just once, add its ID; `.env` is then ignored:

```bash
./psx update <spreadsheet-id>
./psx dry-run <spreadsheet-id>
```

The shortcut just runs the Python script, which you can also call directly:

```bash
.venv/bin/python update_performance.py            # same as ./psx update
.venv/bin/python update_performance.py --dry-run  # same as ./psx dry-run
```

Example output:

```
Refilling 2026-09-11 to 2026-10-10 (writing to sheet)

Date           Portfolio Value     KSE-100  KSE-100 %   Change vs sheet
2026-10-07          283,591.85   50,738.28     0.07%   unchanged
2026-10-08          282,308.29   50,395.63    -0.68%   unchanged
2026-10-09          281,860.05   50,289.49    -0.21%   unchanged

Check: PSX official KSE-100 on 2026-10-09 = 167,089.27, rebuilt = 167,089.29

Updated 21 trading day(s) in 'Daily Performance'.
```

The **Change vs sheet** column shows what each run changed:

- `unchanged`: the sheet already had this value.
- `new row`: a trading day that wasn't in the sheet yet.
- `value was …`: the portfolio value changed, usually because you added or edited trades for that period.

**When to run it:** any time after the market closes. PSX publishes the day's files at about 5 PM Pakistan time. Weekends and PSX holidays are skipped automatically because PSX publishes no files for them. Running it several times a day is harmless.

---

## Spreadsheet layout

### Trade List (read only)

The script reads columns **A–D** from row 2 down:

| Column | Content | Example |
|---|---|---|
| A | Trade date (a real date, not text) | `2026-10-09` |
| B | Stock: the **PSX ticker first**, optionally followed by a name | `LUCK (Lucky Cement Limited)` |
| C | `Buy` or `Sell` | `Buy` |
| D | Quantity | `50` |

The script uses the text before the first space in column B as the PSX ticker (`LUCK`), so the ticker must match PSX's symbol exactly.

The **Net Money Added** and **Cost of Holdings** formulas on the Daily Performance tab also use these Trade List columns:

- **K:** Net Amount. For a Buy this is gross + charges; for a Sell it's gross − charges.
- **N:** Net Cost Basis Change. Each trade's effect on the cost of what you hold, using the average-cost method.

### Daily Performance (written by the script)

The script writes **only columns A, B, E and F**. Every other column is a formula that recalculates automatically. Never type into this tab.

| Column | Name | Written by | Meaning |
|---|---|---|---|
| A | Date | script | Trading day |
| B | Portfolio Value | script | Shares held at that day's close × closing price |
| C | Net Money Added | formula | Buys (incl. charges) − sells (after charges) that day |
| D | My Return % (incl. dividends) | formula | Your return that day, including dividends on their ex-date, excluding money added or withdrawn |
| E | KSE-100 | script | KSE-100 closing level (the headline, total return KSE100 index) |
| F | KSE-100 % | script | KSE-100 daily change |
| G | Difference | formula | D − F (positive = you beat the index that day) |
| H | My Return Since Start | formula | Daily returns compounded since your first trade |
| I | KSE-100 Since Start | formula | KSE-100 daily changes compounded over the same days |
| J | Ahead / Behind | formula | H − I |
| K | Dividends (ex-date, after tax) | formula | From the Dividend summary tab, on the ex-date |
| L | Cost of Holdings | formula | What the shares held that day cost (incl. charges) |
| M | Return on Cost % | formula | B ÷ L − 1, the figure most broker apps show |
| N | Chart label: My Return (helper) | formula | Value of H shown on the chart, filled every 5th trading day (counting back from the latest) |
| O | Chart label: KSE-100 (helper) | formula | Same for I |

The chart next to the table plots H and I. It shows labels taken from columns N and O: the latest value plus one per week, so the values are visible without hovering and the labels don't overlap. To label more or fewer points, change the `5` in the N and O formulas.

Formulas for a fresh copy of the tab (enter in row 2; they fill down automatically):

```text
C2: =MAP(A2:A,LAMBDA(day,IF(day="","",SUMIFS('Trade List'!$K$2:$K,'Trade List'!$A$2:$A,day,'Trade List'!$C$2:$C,"Buy")-SUMIFS('Trade List'!$K$2:$K,'Trade List'!$A$2:$A,day,'Trade List'!$C$2:$C,"Sell"))))
D2: =MAP(SEQUENCE(ROWS(A2:A)),LAMBDA(idx,IF(INDEX(A2:A,idx)="","",LET(val,INDEX(B2:B,idx),flow,INDEX(C2:C,idx),div,N(INDEX(K2:K,idx)),prev,IF(idx=1,0,INDEX(B2:B,idx-1)),IFERROR((val-prev-flow+div)/(prev+MAX(flow,0)),"")))))
G2: =ARRAYFORMULA(IF((A2:A="")+(D2:D="")+(F2:F=""),"",D2:D-F2:F))
H2: =ARRAYFORMULA(IF(A2:A="","",SCAN(1,IF(ISNUMBER(D2:D),D2:D,0),LAMBDA(acc,ret,acc*(1+ret)))-1))
I2: =ARRAYFORMULA(IF(A2:A="","",SCAN(1,IF(ISNUMBER(F2:F),F2:F,0),LAMBDA(acc,ret,acc*(1+ret)))-1))
J2: =ARRAYFORMULA(IF(A2:A="","",H2:H-I2:I))
K2: =MAP(A2:A,LAMBDA(day,IF(day="","",SUMIFS('Dividend summary'!$H$8:$H,'Dividend summary'!$B$8:$B,day))))
L2: =MAP(A2:A,LAMBDA(day,IF(day="","",SUMIFS('Trade List'!$N$2:$N,'Trade List'!$A$2:$A,"<="&day))))
M2: =ARRAYFORMULA(IF(A2:A="","",IFERROR(B2:B/L2:L-1,"")))
N2: =MAP(SEQUENCE(ROWS(A2:A)),LAMBDA(idx,IF(INDEX(A2:A,idx)="","",IF(MOD(COUNT(A2:A)-idx,5)=0,TEXT(INDEX(H2:H,idx),"+0.0%;-0.0%;0.0%"),""))))
O2: =MAP(SEQUENCE(ROWS(A2:A)),LAMBDA(idx,IF(INDEX(A2:A,idx)="","",IF(MOD(COUNT(A2:A)-idx,5)=0,TEXT(INDEX(I2:I,idx),"+0.0%;-0.0%;0.0%"),""))))
```

---

## Charts tab

Four charts, each with its key numbers to the right: summary figures in columns S–T, the monthly table in N–Q (rows 3–70), and the per-stock table in N–V (from row 72). They update by themselves after each `./psx update`.

| # | Chart | What it answers | Key numbers next to it |
|---|---|---|---|
| 1 | **Monthly return: me vs KSE-100** (columns) | Do I beat the market consistently, or thanks to one good month? | Months and days I beat KSE-100, best and worst month. Monthly table in columns N–Q. |
| 2 | **Portfolio value vs money invested** (lines) | How much of my growth is new money and how much is gain? The gap between the lines is the gain or loss in rupees. | Latest value, cost, gain or loss in rupees, return on cost |
| 3 | **Drawdown** (area) | How far below its previous high is each line? A measure of risk: smaller drops than KSE-100 mean my picks were less risky. | Worst drop and current drop from peak, for me and for KSE-100 |
| 4 | **What drove my return, by stock** (stacked columns) | Which stocks made or lost money since my first trade? Each column stacks unrealized P/L, realized P/L and dividends, with the total on top. | Per-stock table: shares held, latest close, market value, unrealized, realized, dividends, total |

How they're calculated:

- **Monthly return** compounds that month's daily *My Return %* and *KSE-100 %* from Daily Performance, so the months multiply up to the "since start" figures.
- **Drawdown** = (1 + return since start) ÷ (highest value of that so far) − 1, counted from your starting point. The series are in the hidden **Charts_Data** tab.
- **Unrealized P/L** = shares held × latest close − cost of those shares (incl. charges, from Portfolio Summary). **Realized P/L** comes from Portfolio Summary. **Dividends** are the after-tax amounts in Dividend summary. Unrealized P/L across all stocks adds up to the rupee gain or loss in chart 2.

The per-stock table, like Portfolio Summary, has room for 20 stocks. The monthly table has room for 67 months; it stops at row 70 so it doesn't run into the per-stock table below it.

If you move a table, its formulas and the chart that uses it need updating: ask for help or rebuild from `template.json`.

---

## Changing the sheet's structure

If you change the tracker sheet itself (new columns, formulas, formatting or charts) and want new copies to include the change:

```bash
./psx export-template
```

This rewrites `template.json` from the sheet in `SPREADSHEET_ID`. Values in Trade List (row 2 down), Dividend summary (row 8 down), Daily Performance (row 2 down) and Latest Prices (row 2 down) count as personal data and are left out; formulas in those rows are kept. Commit the updated `template.json`.

Two rules keep `./psx update` working:

- Keep the Daily Performance columns in place. The script writes to columns **A, B, E and F**.
- The script rewrites **Latest Prices** columns A–C on every run, so don't put anything else on that tab.
- Keep Trade List columns **A–D** (date, stock, Buy/Sell, quantity), plus **K** and **N**, which the Daily Performance formulas use.

---

## How the numbers are calculated

### My Return % (time-weighted, including dividends)

A plain "value today vs value yesterday" would count new money as profit: buy 50,000 of shares and your value jumps 50,000. The daily return therefore removes the money you put in or took out, and adds back dividends:

```
My Return % = (Value today − Value yesterday − Net Money Added + Dividends) ÷ (Value yesterday + Money added that day)
```

- **Dividends** are the after-tax amounts from the Dividend summary tab, counted on their **ex-date** (column K). On that day the stock's price drops by roughly the dividend; adding the dividend back means the drop isn't counted as a loss. Keep the Dividend summary up to date (ex-date and after-tax amount), or your return will be understated.

- Money added (buys) counts as invested from the start of the day. That way, the move from your purchase price to the closing price counts as that day's return.
- Money withdrawn (sells) counts at the end of the day.
- Charges are part of Net Money Added, so they reduce your return.

Compounding these daily returns gives **My Return Since Start**. This method, the time-weighted return, is how funds compare themselves with an index, and it's the only fair way to compare with KSE-100, which never adds or withdraws money.

### Return on Cost % (what your broker shows)

```
Return on Cost % = Portfolio Value ÷ Cost of Holdings − 1
```

This answers "how much have I made or lost on the money in my current holdings?" It usually differs from My Return Since Start because it depends on **when** you invested. Rupees added just before a market fall pull it down more than they pull down the time-weighted return.

| Question | Use |
|---|---|
| How much money am I up or down? | Return on Cost % |
| Are my stock picks beating the market? | My Return Since Start vs KSE-100 Since Start |

### KSE-100

PSX publishes two versions of the index ([PSX brochure](https://www.psx.com.pk/psx/themes/psx/uploads/KSE-100-and-KSE100-PR-Brochure-Jun-2025-Updated.pdf)):

- **KSE100**, the headline number (≈165,000 in Oct 2026), is a **total return** index: cash dividends are treated as reinvested.
- **KSE100PR** is the **price-only** version (≈50,000).

The tracker compares against the headline **KSE100**, because *My Return %* also includes your dividends. That's a like-for-like comparison: *"would I have done better in a KSE-100 index fund?"*

**Where the history comes from.** PSX's own history service can't be used by scripts (it returns *403 Forbidden*), so the script reads KSE-100's daily closes from **sarmaaya.pk**, a public price-history address that needs no login. Column E is that day's close and column F is the change from the previous close. Its figures can differ from PSX's by a few paisa of rounding (e.g. 181,629.37 vs 181,629.27 on 8 July 2026).

**Backup: rebuilding from PSX's files.** For any day sarmaaya doesn't have yet (for example, today, before it updates), or if it can't be reached, the script rebuilds the day's change itself from PSX's daily index file, using each KSE-100 stock's free-float shares × closing price vs × previous closing price:

```
KSE-100 % = Σ (free-float shares × close) ÷ Σ (free-float shares × previous close) − 1
```

On a stock's ex-dividend date, PSX lowers its *previous close* by the dividend (and adjusts it for splits and bonus shares). So the dividend drop isn't counted, which is exactly how a total return index works. That's why this rebuild tracks the headline KSE100, not KSE100PR (which fell about 1.2 points more from July to October 2026 because it leaves dividends out).

One correction is needed for splits and bonus shares: on that day PSX's index file already has the stock's new price but still its old share count. The script detects this (the previous close was adjusted by more than any dividend would) and scales the share count to match. With that, the rebuilt daily change matched PSX's official KSE-100 change on every trading day from 8 July to 12 October 2026, checked against a published closing-price history.

The rebuild also runs on days sarmaaya has, as a cross-check: if the two daily changes differ by more than 0.05 points, the output says *please check*. The **Source** column in the output shows which was used for each day. Each run also compares the sheet's latest level with PSX's official KSE-100 close and prints both.

The index level in column E continues from the previous row's level. On a brand-new sheet, it works backward from PSX's official close.

---

## Data sources

From the free, public **PSX Data Portal** (`dps.psx.com.pk`):

| File | Used for |
|---|---|
| `/download/mkt_summary/YYYY-MM-DD.Z` | Closing and previous closing price of every PSX symbol for the day |
| `/download/indhist/YYYY-MM-DD.xls` | KSE-100 constituents and free-float shares for the day |
| `/indices` | Latest official KSE-100 (KSE100) level, used as a check (and as the starting anchor if no published history is available) |

And from **sarmaaya.pk**:

| Address | Used for |
|---|---|
| `beta-restapi.sarmaaya.pk/api/indices/price-history/KSE100?days=N` | Daily KSE-100 closes for the last N calendar days |

No file for a date means the market was closed. The script treats that as a holiday.

---

## Troubleshooting

| Message / problem | Cause and fix |
|---|---|
| `./psx: Permission denied` | Run `chmod +x psx` once. |
| `The spreadsheet is not blank` | `./psx setup` only works on an empty sheet. Create a new one at <https://sheets.new>. |
| `Missing setting SPREADSHEET_ID` | `.env` is missing or incomplete. Run `cp .env.example .env` and fill it in. |
| `Key file not found` | The JSON key isn't where `GOOGLE_KEY_FILE` points. Check the file name and location. |
| `PermissionError` / `403` from Google | The sheet isn't shared with the service account email as **Editor**, or the Google Sheets API isn't enabled in the Cloud project. |
| `WorksheetNotFound` | A tab name in `.env` doesn't match the sheet exactly (including capitals and spaces). |
| `No PSX closing price on <date> for: XYZ` | The ticker in Trade List column B doesn't match a PSX symbol (check spelling), or the stock was suspended or delisted that day. |
| `Could not anchor the KSE-100 level` | Only on a brand-new, empty Daily Performance tab: PSX's indices page isn't showing the latest trading day yet. Run again after about 5 PM PKT. |
| HTTP `403` from `dps.psx.com.pk` | PSX is blocking the request. PSX blocks Google's servers, so this script can't run inside Google Apps Script. Run it from your own computer. |
| Today's row missing | PSX hadn't published today's files yet. Run again later in the evening. |
| `Warning: could not read KSE-100 history` | sarmaaya.pk was unreachable or changed its format. The run still works using the rebuild; set `KSE100_HISTORY_URL` if the address moved. |
| `(rebuild says …, please check)` | sarmaaya's figure and the rebuild disagree on that day by more than 0.05 points. Usually a corporate action; compare with the PSX portal. |

---

## Security

- **Never commit** `.env` or the service account key. `.gitignore` excludes `.env`, `service-account*.json` and all `*.json` files.
- The service account can only edit spreadsheets shared with it. To revoke access, remove its email from the sheet's **Share** list, or delete its key in Google Cloud (**IAM & Admin → Service Accounts → Keys**).
- If a key is ever exposed (committed, pasted or emailed), delete it in Google Cloud and create a new one.

---

## Limitations

- **Splits and bonus shares** aren't detected automatically. Record bonus shares in Trade List as a `Buy` at price `0` so share counts stay correct.
- **Dividends** count in *My Return %* only if they are entered in the Dividend summary tab with their ex-date. The per-share amount PSX deducts on the ex-date is the gross dividend, while your return uses the after-tax amount you actually receive, so withholding tax counts against you, as it does in real life.
- Each row uses **closing prices**. Intraday moves don't affect the numbers, except that the move from your buy price to the close counts on the day you buy.
- Data depends on the PSX Data Portal staying available and keeping its file formats.
