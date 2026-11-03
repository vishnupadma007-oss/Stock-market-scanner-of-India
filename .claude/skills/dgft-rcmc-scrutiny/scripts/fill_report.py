"""Fill the Spices Board inspection report template.

Usage: python3 fill_report.py <template.docx> <values.json> <out.docx> [--font-size 9]

values.json maps table row numbers (0-32, see references/scrutiny_and_report.md)
to a list of lines for the answer column, e.g. {"6": ["02-11-2026"], "30": ["YES"]}.
Rows not listed keep the template text.
"""
import argparse
import json

import docx
import docx.oxml.ns
from docx.shared import Pt

FONT = 'Bookman Old Style'


def set_cell(table, row, lines, size):
    cell = table.rows[row].cells[2]
    paras = cell.paragraphs
    base = paras[0]
    for p in paras[1:]:
        p._element.getparent().remove(p._element)
    for r in list(base.runs):
        r._element.getparent().remove(r._element)
    for i, line in enumerate(lines):
        p = base if i == 0 else cell.add_paragraph()
        if i:
            p.paragraph_format.alignment = base.paragraph_format.alignment
        run = p.add_run(line)
        run.font.name = FONT
        fonts = run._element.get_or_add_rPr().get_or_add_rFonts()
        for attr in ('w:ascii', 'w:hAnsi', 'w:cs', 'w:eastAsia'):
            fonts.set(docx.oxml.ns.qn(attr), FONT)
        run.font.size = Pt(size)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('template')
    ap.add_argument('values')
    ap.add_argument('out')
    ap.add_argument('--font-size', type=float, default=9)
    a = ap.parse_args()
    doc = docx.Document(a.template)
    table = doc.tables[0]
    with open(a.values, encoding='utf-8') as f:
        values = json.load(f)
    for row, lines in sorted(values.items(), key=lambda kv: int(kv[0])):
        if isinstance(lines, str):
            lines = [lines]
        set_cell(table, int(row), lines, a.font_size)
    doc.save(a.out)
    print('saved', a.out)


if __name__ == '__main__':
    main()
