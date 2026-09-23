"""Builds Session_Pullback_Risk_Toolkit.xlsx: position sizing calculator,
daily/weekly risk tracker, trade journal, and a rules reference sheet - all
matching the defaults in day-trading-system/PLAYBOOK.md.

Run once to (re)generate the workbook, then run recalc.py on the output.
"""
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

FONT_NAME = "Arial"
BLUE = Font(name=FONT_NAME, color="0000FF")
BLACK = Font(name=FONT_NAME, color="000000")
BOLD = Font(name=FONT_NAME, bold=True)
TITLE_FONT = Font(name=FONT_NAME, bold=True, size=14)
HEADER_FONT = Font(name=FONT_NAME, bold=True, color="FFFFFF")
WARN_FONT = Font(name=FONT_NAME, bold=True, color="CC0000")

YELLOW_FILL = PatternFill("solid", fgColor="FFFF00")
HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
SECTION_FILL = PatternFill("solid", fgColor="D9E1F2")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

PCT_FMT = "0.00%"
MONEY_FMT = "$#,##0.00;($#,##0.00);-"
NUM_FMT = "#,##0.00;(#,##0.00);-"
INT_FMT = "#,##0;(#,##0);-"


def style_input(cell):
    cell.font = BLUE
    cell.fill = YELLOW_FILL
    cell.border = BORDER


def style_formula(cell, number_format=None):
    cell.font = BLACK
    cell.border = BORDER
    if number_format:
        cell.number_format = number_format


def set_col_widths(ws: Worksheet, widths: dict):
    for col, w in widths.items():
        ws.column_dimensions[col].width = w


def label(ws, cell_ref, text, bold=False):
    c = ws[cell_ref]
    c.value = text
    c.font = BOLD if bold else Font(name=FONT_NAME)
    return c


def build_rules_sheet(wb: Workbook):
    ws = wb.active
    ws.title = "Rules Reference"
    ws.sheet_view.showGridLines = False
    set_col_widths(ws, {"A": 34, "B": 20, "C": 62})

    ws["A1"] = "Session Pullback System (SPS) - Conservative Risk Defaults"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = "Spot crypto, top-10-by-market-cap majors, no leverage. Full rules: PLAYBOOK.md. Every number here is a hypothesis to validate on your own data - not a guarantee."
    ws["A2"].font = Font(name=FONT_NAME, italic=True, size=9, color="666666")

    headers = ["Control", "Default", "Hard Ceiling / Notes"]
    for i, h in enumerate(headers):
        c = ws.cell(row=4, column=1 + i, value=h)
        c.font = HEADER_FONT
        c.fill = HEADER_FILL
        c.border = BORDER

    rows = [
        ("Risk per trade", "0.4% of equity", "0.5% hard ceiling"),
        ("Max entries per 4H block", "2", "3 hard ceiling"),
        ("Max concurrent positions", "1", "1"),
        ("Daily loss limit", "1.2% of equity (~3R)", "Stop trading for the day, no exceptions"),
        ("Weekly loss limit", "3.0% of equity", "Any rolling 7-day window (crypto trades every day) - stop, review before resuming"),
        ("Consecutive-loss circuit breaker", "2 losses in a block", "Stop trading that block"),
        ("Minimum reward:risk to enter", "1.5R", "Do not take a trade below this"),
        ("Default target", "2.0R", "Or 127.2% fib extension, whichever is closer"),
        ("Move stop to breakeven at", "+1.0R", "Also take partial profit (default 50%) here"),
        ("Minimum stop distance", "1.0x 5m ATR", "Tighter = skip the trade, don't force it"),
        ("No new entries", "First 10 min / last 20 min of block", "Of each 4-hour session block (00:00/04:00/08:00/12:00/16:00/20:00 UTC)"),
        ("Hard time-stop", "End of every 4H block", "Flatten win or lose - not optional"),
        ("Instrument", "Spot, top-10-by-market-cap majors (BTC/ETH first)", "Major exchange, USDT/USD pair - not stablecoins, not blind top-10"),
        ("Leverage", "1x (spot, no leverage)", "If using perpetuals: cap at 2x, never above 3x - liquidation is not a stop"),
    ]
    r = 5
    for control, default, note in rows:
        ws.cell(row=r, column=1, value=control).font = Font(name=FONT_NAME)
        ws.cell(row=r, column=1).border = BORDER
        c2 = ws.cell(row=r, column=2, value=default)
        c2.font = BOLD
        c2.border = BORDER
        c2.alignment = Alignment(horizontal="center")
        c3 = ws.cell(row=r, column=3, value=note)
        c3.font = Font(name=FONT_NAME, size=10, color="444444")
        c3.border = BORDER
        c3.alignment = Alignment(wrap_text=True)
        r += 1

    r += 1
    ws.cell(row=r, column=1, value="The five rules that matter most").font = Font(name=FONT_NAME, bold=True, size=12)
    r += 1
    golden = [
        "1. The daily loss limit is checked BEFORE every new entry, not just at end of day. The next setup after a loss always looks compelling - it isn't special. Stop anyway.",
        "2. Never add to a loser. Never move a stop to give a trade \"more room.\"",
        "3. The stop only tightens, never widens, and is never removed.",
        "4. The hard time-stop overrides everything, including a trade that's currently winning.",
        "5. A rule you didn't follow doesn't count as evidence for or against the system - log it honestly in the Trade Journal tab.",
    ]
    for line in golden:
        ws.cell(row=r, column=1, value=line).font = Font(name=FONT_NAME, size=10)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)
        ws.cell(row=r, column=1).alignment = Alignment(wrap_text=True)
        ws.row_dimensions[r].height = 28
        r += 1


def build_position_size_sheet(wb: Workbook):
    ws = wb.create_sheet("Position Size Calc")
    ws.sheet_view.showGridLines = False
    set_col_widths(ws, {"A": 32, "B": 20, "C": 4, "D": 48})

    ws["A1"] = "Position Size Calculator"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = "Fill in the yellow cells before every trade. Do not take the trade if row 20 or row 24 say not to."
    ws["A2"].font = Font(name=FONT_NAME, italic=True, size=9, color="666666")

    label(ws, "A4", "INPUTS", bold=True)
    ws["A4"].fill = SECTION_FILL
    ws["B4"].fill = SECTION_FILL

    fields = [
        ("A5", "Account Equity ($)", "B5", 25000, MONEY_FMT),
        ("A6", "Risk % per Trade", "B6", 0.004, PCT_FMT),
        ("A7", "Entry Price", "B7", 60000.00, NUM_FMT),
        ("A8", "Stop Price", "B8", 59700.00, NUM_FMT),
        ("A9", "Target R Multiple", "B9", 2.0, "0.0\"R\""),
        ("A10", "Allow Fractional Size? (Y/N)", "B10", "Y", None),
        ("A11", "Current 5-min ATR (optional, for stop-floor check)", "B11", 180.0, NUM_FMT),
        ("A12", "Round-Trip Fee % (entry + exit combined)", "B12", 0.002, PCT_FMT),
    ]
    for lbl_ref, text, val_ref, default, fmt in fields:
        label(ws, lbl_ref, text)
        c = ws[val_ref]
        c.value = default
        style_input(c)
        if fmt:
            c.number_format = fmt

    label(ws, "A14", "RESULTS", bold=True)
    ws["A14"].fill = SECTION_FILL
    ws["B14"].fill = SECTION_FILL

    results = [
        ("A15", "Risk $ (equity x risk %)", "B15", "=B5*B6", MONEY_FMT),
        ("A16", "Stop Distance ($)", "B16", "=ABS(B7-B8)", NUM_FMT),
        ("A17", "Direction (Long/Short)", "B17", '=IF(B7>B8,"LONG","SHORT")', None),
        ("A18", "Raw Position Size (coins)", "B18", "=IFERROR(B15/B16,0)", "#,##0.0000"),
        ("A19", "Position Size (use this)", "B19", '=IF(UPPER(B10)="Y",B18,ROUNDDOWN(B18,0))', "#,##0.0000"),
        ("A20", "Position $ Value (notional)", "B20", "=B19*B7", MONEY_FMT),
        ("A21", "R:R Check (min 1.5R)", "B21", '=IF(B9>=1.5,"OK","BELOW MINIMUM - DO NOT TAKE")', None),
        ("A22", "Risk % Ceiling Check (max 0.5%)", "B22", '=IF(B6>0.005,"ABOVE HARD CEILING - REDUCE SIZE","OK")', None),
        ("A23", "Target Price", "B23", '=IF(B17="LONG",B7+B16*B9,B7-B16*B9)', NUM_FMT),
        ("A24", "Potential Reward $ (at target, before fees)", "B24", "=B19*B16*B9", MONEY_FMT),
        ("A25", "Estimated Fee Cost $ (entry+exit)", "B25", "=B20*B12", MONEY_FMT),
        ("A26", "Stop-Floor Check (min 1.0x ATR)", "B26", '=IF(B11=0,"",IF(B16/B11>=1,"OK","STOP TOO TIGHT - SKIP TRADE"))', None),
        ("A27", "Breakeven Trigger Price (+1R)", "B27", '=IF(B17="LONG",B7+B16,B7-B16)', NUM_FMT),
        ("A28", "Spot Capital Check (no leverage)", "B28", '=IF(B20>B5,"CAPPED BY EQUITY - see row 29","OK")', None),
        ("A29", "Max Position Achievable at Equity Cap", "B29", "=MIN(B19,B5/B7)", "#,##0.0000"),
    ]
    for lbl_ref, text, val_ref, formula, fmt in results:
        label(ws, lbl_ref, text)
        c = ws[val_ref]
        c.value = formula
        style_formula(c, fmt)

    for warn_cell in ("B21", "B22", "B26", "B28"):
        ws[warn_cell].font = BOLD

    ws["D4"] = "Notes"
    ws["D4"].font = BOLD
    ws["D5"] = (
        "Position sizing formula: risk_dollars = equity x risk%; "
        "position_size = risk_dollars / |entry - stop| (fractional coin size - "
        "round down to your exchange's lot/step size). See PLAYBOOK.md section 9."
    )
    ws["D5"].alignment = Alignment(wrap_text=True)
    ws["D6"] = "Never override row 21 or row 26's warning to force a trade in. A setup with no room for a real stop is not a trade."
    ws["D6"].alignment = Alignment(wrap_text=True)
    ws["D7"] = "Row 12/25: set the fee % to your actual exchange taker fee (spot majors are commonly ~0.1% per fill = 0.2% round trip). This is an estimate, not what the backtester charges per-fill."
    ws["D7"].alignment = Alignment(wrap_text=True)
    ws["D8"] = "Row 28: on a spot (no-leverage) account you can't buy more $ of a coin than your cash - a tight ATR stop on a high-priced coin like BTC can imply a position size worth more than your account. If row 28 flags this, use row 29's size instead - your actual dollar risk will be lower than the target risk %, which is safe, just under-target, not a reason to add leverage."
    ws["D8"].alignment = Alignment(wrap_text=True)
    ws.merge_cells("D5:D12")
    ws.merge_cells("D6:D12")
    ws.merge_cells("D7:D12")
    ws.merge_cells("D8:D13")


def build_risk_tracker_sheet(wb: Workbook):
    ws = wb.create_sheet("Daily-Weekly Risk Tracker")
    ws.sheet_view.showGridLines = False
    set_col_widths(ws, {"A": 34, "B": 18, "C": 4, "D": 34, "E": 18})

    ws["A1"] = "Daily & Weekly Risk Tracker"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = "Update the date/equity inputs each session. Pulls realized P&L from the Trade Journal tab automatically."
    ws["A2"].font = Font(name=FONT_NAME, italic=True, size=9, color="666666")

    label(ws, "A4", "TODAY", bold=True)
    ws["A4"].fill = SECTION_FILL
    ws["B4"].fill = SECTION_FILL
    label(ws, "A5", "Today's Date")
    c = ws["B5"]
    c.value = "=TODAY()"
    style_input(c)
    c.number_format = "yyyy-mm-dd"
    label(ws, "A6", "Day Start Equity ($)")
    style_input(ws["B6"])
    ws["B6"].value = 25000
    ws["B6"].number_format = MONEY_FMT

    label(ws, "A7", "Realized P&L Today ($)")
    c = ws["B7"]
    c.value = "=SUMIFS('Trade Journal'!S5:S500,'Trade Journal'!A5:A500,B5)"
    style_formula(c, MONEY_FMT)
    label(ws, "A8", "Daily Loss %")
    c = ws["B8"]
    c.value = "=IFERROR(B7/B6,0)"
    style_formula(c, PCT_FMT)
    label(ws, "A9", "Daily Loss Limit")
    c = ws["B9"]
    c.value = -0.012
    style_formula(c, PCT_FMT)
    label(ws, "A10", "Status")
    c = ws["B10"]
    c.value = '=IF(B8<=B9,"STOP - DAILY LIMIT HIT","OK")'
    style_formula(c)
    c.font = WARN_FONT

    label(ws, "A12", "Trades taken this block")
    style_input(ws["B12"])
    ws["B12"].value = 0
    ws["B12"].number_format = INT_FMT
    label(ws, "A13", "Max entries per block")
    c = ws["B13"]
    c.value = 2
    style_formula(c, INT_FMT)
    label(ws, "A14", "Consecutive losses this block")
    style_input(ws["B14"])
    ws["B14"].value = 0
    ws["B14"].number_format = INT_FMT
    label(ws, "A15", "Consecutive-loss breaker")
    c = ws["B15"]
    c.value = 2
    style_formula(c, INT_FMT)
    label(ws, "A16", "Block Status")
    c = ws["B16"]
    c.value = '=IF(B14>=B15,"STOP - CONSECUTIVE LOSS BREAKER",IF(B12>=B13,"STOP - MAX ENTRIES REACHED","OK TO TRADE"))'
    style_formula(c)
    c.font = WARN_FONT

    label(ws, "D4", "THIS WEEK", bold=True)
    ws["D4"].fill = SECTION_FILL
    ws["E4"].fill = SECTION_FILL
    label(ws, "D5", "Week Start Date (any 7-day window)")
    style_input(ws["E5"])
    ws["E5"].number_format = "yyyy-mm-dd"
    label(ws, "D6", "Week End Date (crypto trades every day)")
    style_input(ws["E6"])
    ws["E6"].number_format = "yyyy-mm-dd"
    label(ws, "D7", "Week Start Equity ($)")
    style_input(ws["E7"])
    ws["E7"].value = 25000
    ws["E7"].number_format = MONEY_FMT

    label(ws, "D8", "Realized P&L This Week ($)")
    c = ws["E8"]
    c.value = "=SUMIFS('Trade Journal'!S5:S500,'Trade Journal'!A5:A500,\">=\"&E5,'Trade Journal'!A5:A500,\"<=\"&E6)"
    style_formula(c, MONEY_FMT)
    label(ws, "D9", "Weekly Loss %")
    c = ws["E9"]
    c.value = "=IFERROR(E8/E7,0)"
    style_formula(c, PCT_FMT)
    label(ws, "D10", "Weekly Loss Limit")
    c = ws["E10"]
    c.value = -0.03
    style_formula(c, PCT_FMT)
    label(ws, "D11", "Status")
    c = ws["E11"]
    c.value = '=IF(E9<=E10,"STOP - WEEKLY LIMIT HIT. Review before resuming.","OK")'
    style_formula(c)
    c.font = WARN_FONT

    ws["A18"] = "Reminder: this tracker reads REALIZED P&L only (closed trades from the Trade Journal). An open position's unrealized loss is not yet counted here - do not use that as a loophole."
    ws["A18"].alignment = Alignment(wrap_text=True)
    ws.merge_cells("A18:E19")
    ws["A18"].font = Font(name=FONT_NAME, italic=True, size=9, color="666666")


TRADE_JOURNAL_HEADERS = [
    "Date", "Block Start", "Symbol", "Side", "4H Bias\nConfirmed?", "Fib+VWAP/EMA\nConfluence?",
    "Entry Time", "Entry Price", "Stop Price", "Target Price", "Stop Distance", "R:R at Entry",
    "Position Size\n(coins)", "Risk $", "Risk % of Equity", "Exit Time", "Exit Price", "Exit Reason",
    "Realized P&L $", "R Multiple", "Breakeven\nMoved?", "All Rules\nFollowed?", "Notes",
]


def build_trade_journal_sheet(wb: Workbook):
    ws = wb.create_sheet("Trade Journal")
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "A5"

    ws["A1"] = "Trade Journal"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = "Log every trade taken, and every A+ setup correctly skipped due to a filter. Column O uses the equity in B3."
    ws["A2"].font = Font(name=FONT_NAME, italic=True, size=9, color="666666")

    label(ws, "A3", "Account Equity (for Risk % of Equity column)")
    style_input(ws["B3"])
    ws["B3"].value = 25000
    ws["B3"].number_format = MONEY_FMT

    header_row = 4
    for i, h in enumerate(TRADE_JOURNAL_HEADERS):
        c = ws.cell(row=header_row, column=1 + i, value=h)
        c.font = HEADER_FONT
        c.fill = HEADER_FILL
        c.border = BORDER
        c.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
    ws.row_dimensions[header_row].height = 32

    widths = [12, 11, 10, 8, 11, 11, 11, 11, 11, 11, 12, 10, 11, 11, 11, 11, 11, 13, 12, 10, 10, 10, 30]
    for i, w in enumerate(widths):
        ws.column_dimensions[get_column_letter(1 + i)].width = w

    n_rows = 200
    first_data_row = 5
    last_data_row = first_data_row + n_rows - 1
    for r in range(first_data_row, last_data_row + 1):
        # K Stop Distance
        c = ws.cell(row=r, column=11, value=f"=IF(AND(H{r}<>\"\",I{r}<>\"\"),ABS(H{r}-I{r}),\"\")")
        style_formula(c, NUM_FMT)
        # L R:R at entry
        c = ws.cell(row=r, column=12, value=f"=IFERROR(ABS(J{r}-H{r})/K{r},\"\")")
        style_formula(c, "0.00\"R\"")
        # N Risk $
        c = ws.cell(row=r, column=14, value=f"=IF(AND(K{r}<>\"\",M{r}<>\"\"),K{r}*M{r},\"\")")
        style_formula(c, MONEY_FMT)
        # O Risk % of equity
        c = ws.cell(row=r, column=15, value=f"=IFERROR(N{r}/$B$3,\"\")")
        style_formula(c, PCT_FMT)
        # S Realized P&L input (manual - actual fills/commissions/slippage vary) -> leave as input
        style_input(ws.cell(row=r, column=19))
        ws.cell(row=r, column=19).number_format = MONEY_FMT
        # T R multiple
        c = ws.cell(row=r, column=20, value=f"=IFERROR(S{r}/N{r},\"\")")
        style_formula(c, "0.00\"R\"")

        # Inputs: A,B,C,D,E,F,G,H,I,J,M,P,Q,R,U,V,W
        for col in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 13, 16, 17, 18, 21, 22, 23]:
            cell = ws.cell(row=r, column=col)
            cell.font = Font(name=FONT_NAME)
            cell.border = BORDER
        ws.cell(row=r, column=1).number_format = "yyyy-mm-dd"
        ws.cell(row=r, column=7).number_format = "hh:mm"
        ws.cell(row=r, column=16).number_format = "hh:mm"
        for col in (8, 9, 10):
            ws.cell(row=r, column=col).number_format = NUM_FMT
        ws.cell(row=r, column=13).number_format = "#,##0.0000"
        ws.cell(row=r, column=17).number_format = NUM_FMT

    # Example row (row 5) with realistic values, clearly marked
    ex = first_data_row
    example = {
        1: "2026-01-15", 2: "00:00 UTC", 3: "BTCUSDT", 4: "Long", 5: "Y", 6: "Y",
        7: "00:11", 8: 60420.00, 9: 60120.00, 10: 61020.00, 13: 0.0333,
        16: "00:35", 17: 61020.00, 18: "Target", 19: 19.98, 21: "Y", 22: "Y",
        23: "EXAMPLE ROW - overwrite or delete. Pullback to VWAP + 61.8%, RSI reclaim, vol confirmed. Spot, no leverage, reduced size (validation phase).",
    }
    for col, val in example.items():
        ws.cell(row=ex, column=col).value = val

    # Summary block
    sum_row = last_data_row + 3
    label(ws, f"A{sum_row}", "SUMMARY (this journal)", bold=True)
    ws[f"A{sum_row}"].fill = SECTION_FILL
    stats = [
        ("Total Closed Trades", f'=COUNT(S{first_data_row}:S{last_data_row})'),
        ("Wins", f'=COUNTIF(S{first_data_row}:S{last_data_row},">0")'),
        ("Losses", f'=COUNTIF(S{first_data_row}:S{last_data_row},"<=0")'),
        ("Win Rate", f'=IFERROR(B{sum_row+2}/B{sum_row+1},"")'),
        ("Gross Profit", f'=SUMIF(S{first_data_row}:S{last_data_row},">0")'),
        ("Gross Loss", f'=SUMIF(S{first_data_row}:S{last_data_row},"<0")'),
        ("Net P&L", f'=SUM(S{first_data_row}:S{last_data_row})'),
        ("Profit Factor", f'=IFERROR(B{sum_row+5}/ABS(B{sum_row+6}),"")'),
        ("Average R Multiple (Expectancy)", f'=IFERROR(AVERAGE(T{first_data_row}:T{last_data_row}),"")'),
        ("Trades Where All Rules Followed %", f'=IFERROR(COUNTIF(V{first_data_row}:V{last_data_row},"Y")/B{sum_row+1},"")'),
    ]
    r = sum_row + 1
    fmt_map = {0: INT_FMT, 1: INT_FMT, 2: INT_FMT, 3: PCT_FMT, 4: MONEY_FMT, 5: MONEY_FMT, 6: MONEY_FMT, 7: "0.00", 8: "0.00\"R\"", 9: PCT_FMT}
    for i, (lbl, formula) in enumerate(stats):
        label(ws, f"A{r}", lbl)
        c = ws[f"B{r}"]
        c.value = formula
        style_formula(c, fmt_map[i])
        r += 1


def main():
    wb = Workbook()
    build_rules_sheet(wb)
    build_position_size_sheet(wb)
    build_risk_tracker_sheet(wb)
    build_trade_journal_sheet(wb)
    out = "Session_Pullback_Risk_Toolkit.xlsx"
    wb.save(out)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
