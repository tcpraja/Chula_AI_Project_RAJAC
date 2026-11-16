"""Tiny evaluator for the simple arithmetic formulas in reports/economics_and_energy.xlsx (+ - * / ( ) IF MAX MIN ABS, cross-sheet refs).
Used to check the live Excel formulas without Excel/LibreOffice. Run: python -m src.xl_eval <xlsx> <sheet> <cell>
"""
import re
import sys

import openpyxl

REF = re.compile(r"(?:(?P<sheet>[A-Za-z_]\w*)!)?\$?(?P<col>[A-Z]{1,2})\$?(?P<row>\d+)(?![\w(])")


def _IF(c, a, b):
    return a if c else b


class Book:
    def __init__(self, path):
        self.wb = openpyxl.load_workbook(path)          # formulas, not cached values
        self.memo = {}

    def value(self, sheet, cell):
        key = (sheet, cell)
        if key in self.memo:
            return self.memo[key]
        v = self.wb[sheet][cell].value
        if isinstance(v, str) and v.startswith("="):
            expr = REF.sub(lambda m: f"_v({m.group('sheet') or sheet!r}, {m.group('col') + m.group('row')!r})"
                           if m.group("sheet") else f"_v({sheet!r}, {m.group('col') + m.group('row')!r})", v[1:])
            expr = expr.replace("IF(", "_IF(").replace("MAX(", "max(").replace("MIN(", "min(").replace("ABS(", "abs(")
            v = eval(expr, {"__builtins__": {}}, {"_v": self.value, "_IF": _IF, "max": max, "min": min, "abs": abs})
        self.memo[key] = v
        return v


def main():
    b = Book(sys.argv[1])
    print(b.value(sys.argv[2], sys.argv[3]))


if __name__ == "__main__":
    main()
