"""Assemble the inspection-report PDF pack for DGFT upload (limit 5 MB).

Usage:
  python3 build_pack.py --report report.pdf --out pack.pdf \
      [--last-page-scan scan.jpg] [--signature sig.jpg] \
      [--photos p1.jpg p2.jpg ...] [--photo-caption "M/s X, address | Date of inspection: DD-MM-YYYY"] \
      [--append FILE ...]

--last-page-scan  replace the report's last page with a scanned signed sheet (see scan_page.py)
--signature       stamp a signature image under item 28 on the report's last page,
                  with "VISHNU N / ASSISTANT / SPICES BOARD, BENGALURU" below it
--photos          2 photos per A4 page under "PHOTOGRAPHS TAKEN DURING UNIT INSPECTION"
--append          PDFs or images, in order. Prefix "raster:" to recompress a heavy scanned
                  PDF (120 dpi JPEG), "rot90:" to turn a sideways page/image clockwise,
                  e.g. raster:machinery.pdf  rot90:raster:payroll.pdf  halal.jpg
Needs: pypdf, reportlab, Pillow, numpy, poppler-utils (pdftoppm).
"""
import argparse
import glob
import io
import os
import subprocess
import tempfile

import numpy as np
from PIL import Image, ImageOps
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4, landscape, letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

SIGN_LINES = ['VISHNU N', 'ASSISTANT', 'SPICES BOARD, BENGALURU']


def jpg(im, maxpx=1500, q=65):
    im = ImageOps.exif_transpose(im).convert('RGB')
    im.thumbnail((maxpx, maxpx), Image.LANCZOS)
    b = io.BytesIO()
    im.save(b, 'JPEG', quality=q, optimize=True)
    b.seek(0)
    return ImageReader(b), im.size


def pages_of(pdf_bytes):
    return PdfReader(io.BytesIO(pdf_bytes)).pages


def images_to_pdf(images):
    b = io.BytesIO()
    c = canvas.Canvas(b)
    for im in images:
        r, (w, h) = jpg(im)
        ps = landscape(A4) if w > h else A4
        c.setPageSize(ps)
        m = 18
        s = min((ps[0] - 2 * m) / w, (ps[1] - 2 * m) / h)
        c.drawImage(r, (ps[0] - w * s) / 2, (ps[1] - h * s) / 2, w * s, h * s)
        c.showPage()
    c.save()
    return b.getvalue()


def signature_overlay(sig_path, page):
    """Signature centred under the officer box (item 28) found by text position."""
    ys = []

    def visit(text, cm, tm, fd, fs):
        if 'Name of the Office' in text or 'Bengaluru' in text:
            ys.append(tm[5])
    page.extract_text(visitor_text=visit)
    box_bottom = (min(ys) - 10) if ys else 150
    w0, h0 = float(page.mediabox.width), float(page.mediabox.height)
    g = np.array(Image.open(sig_path).convert('L'))
    ink = np.where(g < 140)
    y0, y1, x0, x1 = ink[0].min(), ink[0].max(), ink[1].min(), ink[1].max()
    crop = g[max(0, y0 - 10):y1 + 10, max(0, x0 - 10):x1 + 10]
    rgba = np.zeros(crop.shape + (4,), np.uint8)
    rgba[..., 0], rgba[..., 1], rgba[..., 2] = 20, 30, 110
    rgba[..., 3] = np.clip((200 - crop.astype(int)) * 255 // 120, 0, 255)
    tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
    Image.fromarray(rgba, 'RGBA').save(tmp.name)
    b = io.BytesIO()
    c = canvas.Canvas(b, pagesize=(w0, h0))
    h = min(88, box_bottom - 50)
    w = h * crop.shape[1] / crop.shape[0]
    cx = w0 * 0.74
    c.drawImage(tmp.name, cx - w / 2, box_bottom - h, w, h, mask='auto')
    c.setFont('Helvetica', 9)
    for i, t in enumerate(SIGN_LINES):
        c.drawCentredString(cx, box_bottom - h - 10 - 11 * i, t)
    c.save()
    os.unlink(tmp.name)
    return pages_of(b.getvalue())[0]


def photo_pages(paths, caption):
    b = io.BytesIO()
    pw, ph = A4
    c = canvas.Canvas(b, pagesize=A4)
    half = (ph - 110) / 2
    for i in range(0, len(paths), 2):
        c.setFont('Helvetica-Bold', 13)
        c.drawCentredString(pw / 2, ph - 40, 'PHOTOGRAPHS TAKEN DURING UNIT INSPECTION')
        if caption:
            c.setFont('Helvetica', 9.5)
            c.drawCentredString(pw / 2, ph - 56, caption)
        for j, f in enumerate(paths[i:i + 2]):
            r, (w, h) = jpg(Image.open(f), 1400, 68)
            top = ph - 75 - j * (half + 5)
            s = min((pw - 60) / w, (half - 10) / h)
            c.drawImage(r, (pw - w * s) / 2, top - h * s, w * s, h * s)
        c.showPage()
    c.save()
    return b.getvalue()


def appended(spec):
    rot = raster = False
    while ':' in spec and spec.split(':', 1)[0] in ('rot90', 'raster'):
        tag, spec = spec.split(':', 1)
        rot |= tag == 'rot90'
        raster |= tag == 'raster'
    if spec.lower().endswith('.pdf') and not raster and not rot:
        return list(PdfReader(spec).pages)
    if spec.lower().endswith('.pdf'):
        d = tempfile.mkdtemp()
        subprocess.run(['pdftoppm', '-r', '120', '-jpeg', '-jpegopt', 'quality=65', spec, d + '/p'], check=True)
        ims = [Image.open(f) for f in sorted(glob.glob(d + '/p-*.jpg'))]
    else:
        ims = [Image.open(spec)]
    if rot:
        ims = [ImageOps.exif_transpose(i).rotate(-90, expand=True) for i in ims]
    return list(pages_of(images_to_pdf(ims)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--report', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--last-page-scan')
    ap.add_argument('--signature')
    ap.add_argument('--photos', nargs='*', default=[])
    ap.add_argument('--photo-caption', default='')
    ap.add_argument('--append', nargs='*', default=[])
    a = ap.parse_args()

    out = PdfWriter()
    rep = list(PdfReader(a.report).pages)
    if a.last_page_scan:
        b = io.BytesIO()
        c = canvas.Canvas(b, pagesize=letter)
        r, _ = jpg(Image.open(a.last_page_scan), 2000, 75)
        c.drawImage(r, 0, 0, letter[0], letter[1])
        c.showPage()
        c.save()
        rep[-1] = pages_of(b.getvalue())[0]
    if a.signature:
        rep[-1].merge_page(signature_overlay(a.signature, rep[-1]))
    for p in rep:
        out.add_page(p)
    if a.photos:
        for p in pages_of(photo_pages(a.photos, a.photo_caption)):
            out.add_page(p)
    for spec in a.append:
        for p in appended(spec):
            out.add_page(p)
    for p in out.pages:
        p.compress_content_streams()
    out.write(a.out)
    mb = os.path.getsize(a.out) / 1e6
    print(f'{a.out}: {len(out.pages)} pages, {mb:.2f} MB' + ('  ** OVER 5 MB: add raster: to heavy appends **' if mb > 5 else ''))


if __name__ == '__main__':
    main()
