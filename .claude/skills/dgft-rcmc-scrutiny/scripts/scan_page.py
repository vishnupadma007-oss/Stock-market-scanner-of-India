"""Turn a phone photo of a printed page into a clean, straight "scanned" page.

Usage: python3 scan_page.py <photo.jpg> <out.jpg> [x1,y1,x2,y2,x3,y3,x4,y4] [--grid grid.jpg]

Corners are TL,TR,BR,BL in original-photo pixels. Without them the paper is
auto-detected, which often fails on glossy/glass tables. Use --grid first to
write a small copy with a coordinate grid (labels are in grid-image pixels;
multiply by the printed scale factor) and read the corners off it.
Output is US-Letter at 300 dpi; blue ink (seal/signature) keeps its colour.
Needs: pip install opencv-python-headless
"""
import argparse

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageOps


def load(path):
    im = ImageOps.exif_transpose(Image.open(path)).convert('RGB')
    return im, cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)


def write_grid(im, out):
    w, h = im.size
    scale = 1020 / h
    sm = im.resize((int(w * scale), 1020))
    d = ImageDraw.Draw(sm)
    for x in range(0, sm.size[0], 50):
        d.line([(x, 0), (x, sm.size[1])], fill=(255, 0, 0))
    for y in range(0, sm.size[1], 50):
        d.line([(0, y), (sm.size[0], y)], fill=(255, 0, 0))
    for x in range(0, sm.size[0], 100):
        for y in range(0, sm.size[1], 100):
            d.text((x + 2, y + 2), f'{x},{y}', fill=(255, 255, 0))
    sm.save(out)
    print(f'grid saved; multiply grid coordinates by {1 / scale:.4f} to get photo pixels')


def detect(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (0, 0, 140), (180, 50, 255))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((81, 81), np.uint8))
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    c = cv2.convexHull(max(cnts, key=cv2.contourArea))
    peri = cv2.arcLength(c, True)
    approx = c
    for eps in (0.01, 0.02, 0.03, 0.05, 0.08):
        approx = cv2.approxPolyDP(c, eps * peri, True)
        if len(approx) == 4:
            break
    if len(approx) != 4:
        approx = cv2.boxPoints(cv2.minAreaRect(c))
    pts = approx.reshape(-1, 2).astype('float32')
    s, d = pts.sum(1), np.diff(pts, axis=1).ravel()
    return pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]


def enhance(img, corners):
    W, H = 2550, 3300
    M = cv2.getPerspectiveTransform(np.float32(corners), np.float32([[0, 0], [W, 0], [W, H], [0, H]]))
    warp = cv2.warpPerspective(img, M, (W, H), flags=cv2.INTER_CUBIC)
    bg = cv2.medianBlur(cv2.dilate(warp, np.ones((15, 15), np.uint8)), 61)
    norm = cv2.divide(warp, bg, scale=255)
    # Levels 110..232 kept real text through glare; stronger settings erased it.
    norm = np.clip((norm.astype(np.float32) - 110) * (255.0 / (232 - 110)), 0, 255).astype(np.uint8)
    gray = cv2.cvtColor(norm, cv2.COLOR_BGR2GRAY)
    gray = np.where(gray > 200, 255, gray).astype(np.uint8)
    blue = cv2.inRange(cv2.cvtColor(norm, cv2.COLOR_BGR2HSV), (90, 60, 0), (140, 255, 255))
    res = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    res[blue > 0] = norm[blue > 0]
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('photo')
    ap.add_argument('out')
    ap.add_argument('corners', nargs='?')
    ap.add_argument('--grid')
    a = ap.parse_args()
    im, img = load(a.photo)
    if a.grid:
        write_grid(im, a.grid)
        return
    if a.corners:
        v = [float(x) for x in a.corners.split(',')]
        corners = [v[0:2], v[2:4], v[4:6], v[6:8]]
    else:
        corners = [list(map(float, p)) for p in detect(img)]
    print('corners TL,TR,BR,BL:', corners)
    cv2.imwrite(a.out, enhance(img, corners), [cv2.IMWRITE_JPEG_QUALITY, 85])
    print('saved', a.out)


if __name__ == '__main__':
    main()
