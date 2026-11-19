"""Convert the Polish Pseudo-words List (Imbir, Spustek & Żygierewicz 2015) xlsx to UTF-8 CSV (values unchanged)."""
import csv
import os

import openpyxl

here = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(here, "Polish_pseudo-words_List_dataset.xlsx")
dst = os.path.join(here, "Polish_pseudo-words_List_dataset.csv")

wb = openpyxl.load_workbook(src, read_only=False, data_only=True)
print("sheets:", [(ws.title, ws.max_row, ws.max_column) for ws in wb.worksheets])
ws = wb.worksheets[0]
rows = [r for r in ws.iter_rows(values_only=True) if any(c is not None for c in r)]
ncol = max(i + 1 for r in rows for i, c in enumerate(r) if c is not None)
with open(dst, "w", encoding="utf-8", newline="") as fh:
    w = csv.writer(fh)
    for r in rows:
        w.writerow(["" if c is None else c for c in r[:ncol]])
print(f"wrote {dst}: {len(rows) - 1} data rows + header, {ncol} columns")
print("header:", rows[0][:ncol])
