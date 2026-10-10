# PSX Tracker

Tracks how a Pakistan Stock Exchange (PSX) portfolio performs **day by day against the KSE-100 index**, inside a Google Sheet.

Brokers usually show only today's change. This script builds a history: one row per trading day with your portfolio's value, your daily return, the KSE-100's daily return, and running totals since you started. Over time you can see whether your stock picks beat the market.

It runs on your computer. Each run:

1. Reads your trades from the **Trade List** tab of your Google Sheet.
2. Downloads PSX's free end-of-day files for each trading day.
3. Prices your holdings at each day's closing prices and works out the KSE-100's daily change.
4. Writes the results to the **Daily Performance** tab. Formulas on that tab calculate everything else.

Run it whenever you like. Each run re-prices the last `DAYS_TO_REFILL` days (30 by default) using your current Trade List, so trades you enter a few days late are picked up automatically. It also fills any gap since the last row.

---

## Contents

- [Requirements](#requirements)
- [One-time setup](#one-time-setup)
- [Configuration (.env)](#configuration-env)
- [Running the script](#running-the-script)
- [Spreadsheet layout](#spreadsheet-layout)
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

### 4. Check that everything works

```bash
./psx dry-run
```

You should see a table of trading days and a line comparing the rebuilt KSE-100 with PSX's official figure. A dry run never writes to the sheet.

---

## Configuration (.env)

All settings that differ between people live in `.env`. That file isn't committed; `.env.example` is the committed template.

| Setting | Required | Default | Description |
|---|---|---|---|
| `SPREADSHEET_ID` | Yes | – | The ID in your sheet's URL: `docs.google.com/spreadsheets/d/`**`<SPREADSHEET_ID>`**`/edit` |
| `GOOGLE_KEY_FILE` | No | `service-account.json` | Path to the service account key, relative to this folder |
| `TRADE_SHEET` | No | `Trade List` | Name of the tab holding your trades |
| `PERF_SHEET` | No | `Daily Performance` | Name of the tab the script writes to |
| `DAYS_TO_REFILL` | No | `30` | How many days back to re-price on every run. Increase it if you often enter trades more than 30 days late. Set it high (e.g. `400`) to rebuild your whole history. |
| `PSX_BASE_URL` | No | `https://dps.psx.com.pk` | PSX Data Portal address. Only change it if PSX moves the portal. |

---

## Running the script

Use the `psx` shortcut from this folder:

```bash
./psx update     # refresh the Daily Performance tab
./psx dry-run    # show what would change, without writing to the sheet
./psx            # list the commands
```

It works from any folder if you give its path, e.g. `~/Desktop/psx-tracker/psx update`.

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

Check: PSX official KSE-100 price index on 2026-10-09 = 50,289.49, rebuilt = 50,289.49

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
| D | My Return % | formula | Your return that day, excluding money added or withdrawn |
| E | KSE-100 (price index) | script | KSE-100 price index (KSE100PR) closing level |
| F | KSE-100 % | script | KSE-100 daily change |
| G | Difference | formula | D − F (positive = you beat the index that day) |
| H | My Return Since Start | formula | Daily returns compounded since your first trade |
| I | KSE-100 Since Start | formula | KSE-100 daily changes compounded over the same days |
| J | Ahead / Behind | formula | H − I |
| K | Dividends (ex-date, after tax) | formula | From the Dividend summary tab, on the ex-date |
| L | Cost of Holdings | formula | What the shares held that day cost (incl. charges) |
| M | Return on Cost % | formula | B ÷ L − 1, the figure most broker apps show |

Formulas for a fresh copy of the tab (enter in row 2; they fill down automatically):

```text
C2: =MAP(A2:A,LAMBDA(day,IF(day="","",SUMIFS('Trade List'!$K$2:$K,'Trade List'!$A$2:$A,day,'Trade List'!$C$2:$C,"Buy")-SUMIFS('Trade List'!$K$2:$K,'Trade List'!$A$2:$A,day,'Trade List'!$C$2:$C,"Sell"))))
D2: =MAP(SEQUENCE(ROWS(A2:A)),LAMBDA(idx,IF(INDEX(A2:A,idx)="","",LET(val,INDEX(B2:B,idx),flow,INDEX(C2:C,idx),prev,IF(idx=1,0,INDEX(B2:B,idx-1)),IFERROR((val-prev-flow)/(prev+MAX(flow,0)),"")))))
G2: =ARRAYFORMULA(IF((A2:A="")+(D2:D="")+(F2:F=""),"",D2:D-F2:F))
H2: =ARRAYFORMULA(IF(A2:A="","",SCAN(1,IF(ISNUMBER(D2:D),D2:D,0),LAMBDA(acc,ret,acc*(1+ret)))-1))
I2: =ARRAYFORMULA(IF(A2:A="","",SCAN(1,IF(ISNUMBER(F2:F),F2:F,0),LAMBDA(acc,ret,acc*(1+ret)))-1))
J2: =ARRAYFORMULA(IF(A2:A="","",H2:H-I2:I))
K2: =MAP(A2:A,LAMBDA(day,IF(day="","",SUMIFS('Dividend summary'!$H$8:$H,'Dividend summary'!$B$8:$B,day))))
L2: =MAP(A2:A,LAMBDA(day,IF(day="","",SUMIFS('Trade List'!$N$2:$N,'Trade List'!$A$2:$A,"<="&day))))
M2: =ARRAYFORMULA(IF(A2:A="","",IFERROR(B2:B/L2:L-1,"")))
```

---

## How the numbers are calculated

### My Return % (time-weighted)

A plain "value today vs value yesterday" would count new money as profit: buy 50,000 of shares and your value jumps 50,000. The daily return therefore removes the money you put in or took out:

```
My Return % = (Value today − Value yesterday − Net Money Added) ÷ (Value yesterday + Money added that day)
```

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

PSX publishes two versions of the index:

- **KSE100**, the headline number, now includes reinvested dividends (a total return index).
- **KSE100PR** is the **price-only** version.

The script compares against **KSE100PR**, because your portfolio value is also price-only (dividends are shown separately in column K).

PSX only publishes **today's** index level, not a history. So the script rebuilds each day's change from PSX's daily index file, using each KSE-100 stock's free-float shares × closing price vs × previous closing price:

```
KSE-100 % = Σ (free-float shares × close) ÷ Σ (free-float shares × previous close) − 1
```

Each run compares the rebuilt figure with PSX's official KSE100PR close for the latest day and prints both. They have matched to the paisa so far.

The index level in column E continues from the previous row's level. On a brand-new sheet, it works backward from PSX's official close.

---

## Data sources

All from the free, public **PSX Data Portal** (`dps.psx.com.pk`):

| File | Used for |
|---|---|
| `/download/mkt_summary/YYYY-MM-DD.Z` | Closing and previous closing price of every PSX symbol for the day |
| `/download/indhist/YYYY-MM-DD.xls` | KSE-100 constituents and free-float shares for the day |
| `/indices` | Latest official KSE100PR level, used as a check and as the starting anchor |

No file for a date means the market was closed. The script treats that as a holiday.

---

## Troubleshooting

| Message / problem | Cause and fix |
|---|---|
| `./psx: Permission denied` | Run `chmod +x psx` once. |
| `Missing setting SPREADSHEET_ID` | `.env` is missing or incomplete. Run `cp .env.example .env` and fill it in. |
| `Key file not found` | The JSON key isn't where `GOOGLE_KEY_FILE` points. Check the file name and location. |
| `PermissionError` / `403` from Google | The sheet isn't shared with the service account email as **Editor**, or the Google Sheets API isn't enabled in the Cloud project. |
| `WorksheetNotFound` | A tab name in `.env` doesn't match the sheet exactly (including capitals and spaces). |
| `No PSX closing price on <date> for: XYZ` | The ticker in Trade List column B doesn't match a PSX symbol (check spelling), or the stock was suspended or delisted that day. |
| `Could not anchor the KSE-100 level` | Only on a brand-new, empty Daily Performance tab: PSX's indices page isn't showing the latest trading day yet. Run again after about 5 PM PKT. |
| HTTP `403` from `dps.psx.com.pk` | PSX is blocking the request. PSX blocks Google's servers, so this script can't run inside Google Apps Script. Run it from your own computer. |
| Today's row missing | PSX hadn't published today's files yet. Run again later in the evening. |

---

## Security

- **Never commit** `.env` or the service account key. `.gitignore` excludes `.env`, `service-account*.json` and all `*.json` files.
- The service account can only edit spreadsheets shared with it. To revoke access, remove its email from the sheet's **Share** list, or delete its key in Google Cloud (**IAM & Admin → Service Accounts → Keys**).
- If a key is ever exposed (committed, pasted or emailed), delete it in Google Cloud and create a new one.

---

## Limitations

- **Splits and bonus shares** aren't detected automatically. Record bonus shares in Trade List as a `Buy` at price `0` so share counts stay correct.
- **Dividends** aren't added to *My Return %*. That keeps it comparable with the price-only KSE-100; dividends are listed in column K.
- Each row uses **closing prices**. Intraday moves don't affect the numbers, except that the move from your buy price to the close counts on the day you buy.
- Data depends on the PSX Data Portal staying available and keeping its file formats.
