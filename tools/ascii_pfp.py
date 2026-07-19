#!/usr/bin/env python3
"""Render assets/pfp.png as an animated ASCII-art SVG (dark + light variants).

Run by hand after changing the avatar:  .venv/bin/python tools/ascii_pfp.py
Self-check:                             .venv/bin/python tools/ascii_pfp.py --self-check
"""
import random
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "pfp.png"

COLS, ROWS = 80, 44
RAMP = " .:-=+*#%@"  # tune here: short ramp keeps high-contrast lineart crisp
FS = 14.0
CHAR_W = FS * 0.6
LINE_H = 15.3  # chosen so COLS*CHAR_W ~= ROWS*LINE_H (source is square)
PAD = 16.0
GROUPS = 4  # column groups per row, so the shimmer reads diagonal not horizontal
GW = COLS // GROUPS
CHURN_PCT = 0.04
SEED = 7

ROW_STEP = 0.06  # draw-in stagger per row
DRAW_TOTAL = ROWS * ROW_STEP

# One dark identity for the whole profile: every widget on the README is themed
# to these three values, so a light variant here would only break the set.
THEME = {"bg": "#0d0d0f", "fg": "#f5f2ea", "accent": "#e0a30c"}


def ramp_grid():
    """Avatar -> per-cell ramp indices. Dark source pixels map to dense chars."""
    img = ImageOps.autocontrast(Image.open(SRC).convert("L")).resize(
        (COLS, ROWS), Image.LANCZOS
    )
    px = img.load()
    top = len(RAMP) - 1
    return [[round((1 - px[x, y] / 255) * top) for x in range(COLS)] for y in range(ROWS)]


def pick_churn(grid, rng):
    """Mid-tone cells only: blanks and solids have no neighbouring char to swap to."""
    cands = [
        (x, y)
        for y in range(ROWS)
        for x in range(COLS)
        if 0 < grid[y][x] < len(RAMP) - 1
    ]
    rng.shuffle(cands)
    return cands[: int(COLS * ROWS * CHURN_PCT)]


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build(grid, churn, rng):
    t = THEME
    w = COLS * CHAR_W + 2 * PAD
    h = ROWS * LINE_H + 2 * PAD
    churn_set = set(churn)

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" '
        f'viewBox="0 0 {w:.1f} {h:.1f}" role="img" aria-label="ASCII portrait">',
        "<style>",
        "text{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,'DejaVu Sans Mono',monospace;"
        f"font-size:{FS}px;fill:{t['fg']}}}",
        ".r{animation:draw .38s ease-out both;animation-delay:var(--d)}",
        "@keyframes draw{from{opacity:0;transform:translateX(-8px)}to{opacity:1;transform:none}}",
        ".g{animation:shimmer 6s linear infinite both;animation-delay:var(--s)}",
        f"@keyframes shimmer{{0%{{fill:{t['accent']}}}6%{{fill:{t['fg']}}}100%{{fill:{t['fg']}}}}}",
        f".churn{{animation:fadein .8s ease-out {DRAW_TOTAL:.2f}s both}}",
        "@keyframes fadein{from{opacity:0}to{opacity:1}}",
        ".ca{animation:ca var(--t) linear infinite both;animation-delay:var(--s)}",
        ".cb{animation:cb var(--t) linear infinite both;animation-delay:var(--s)}",
        "@keyframes ca{0%,49%{opacity:1}50%,100%{opacity:0}}",
        "@keyframes cb{0%,49%{opacity:0}50%,100%{opacity:1}}",
        f".cur{{fill:{t['accent']};animation:walk {DRAW_TOTAL:.2f}s steps({ROWS}) both,"
        "blink 1.1s steps(2) infinite}",
        f"@keyframes walk{{from{{transform:translateY(0)}}to{{transform:translateY({(ROWS - 1) * LINE_H:.1f}px)}}}}",
        "@keyframes blink{50%{opacity:0}}",
        "</style>",
        f'<rect width="100%" height="100%" fill="{t["bg"]}"/>',
    ]

    for y, row in enumerate(grid):
        chars = [RAMP[v] for v in row]
        for x in range(COLS):
            if (x, y) in churn_set:
                chars[x] = " "  # the churn layer draws this cell instead
        yb = PAD + y * LINE_H + FS * 0.8
        out.append(f'<text class="r" y="{yb:.1f}" style="--d:{y * ROW_STEP:.2f}s">')
        for gi in range(GROUPS):
            seg = "".join(chars[gi * GW : (gi + 1) * GW])
            # negative delay = already-running loop, phase-shifted -> travelling band
            shift = -(y * ROW_STEP + gi * 0.25)
            out.append(
                f'<tspan class="g" xml:space="preserve" x="{PAD + gi * GW * CHAR_W:.1f}" '
                f'textLength="{GW * CHAR_W:.1f}" lengthAdjust="spacing" '
                f'style="--s:{shift:.2f}s">{esc(seg)}</tspan>'
            )
        out.append("</text>")

    out.append('<g class="churn">')
    for x, y in churn:
        a, b = RAMP[grid[y][x]], RAMP[grid[y][x] + rng.choice((-1, 1))]
        cx = PAD + x * CHAR_W + CHAR_W / 2
        cy = PAD + y * LINE_H + FS * 0.8
        style = f"--t:{rng.uniform(2.4, 5.2):.2f}s;--s:-{rng.uniform(0, 5):.2f}s"
        for cls, ch in (("ca", a), ("cb", b)):
            out.append(
                f'<text class="{cls}" x="{cx:.1f}" y="{cy:.1f}" text-anchor="middle" '
                f'style="{style}">{esc(ch)}</text>'
            )
    out.append("</g>")

    out.append(
        f'<text class="cur" x="{PAD:.1f}" y="{PAD + FS * 0.8:.1f}">▌</text>'
    )
    out.append("</svg>")
    return "\n".join(out)


def self_check(path):
    """Fails if the ramp threshold silently produced an all-blank or all-solid image."""
    root = ET.parse(path).getroot()
    ns = "{http://www.w3.org/2000/svg}"
    rows = [e for e in root.iter(f"{ns}text") if e.get("class") == "r"]
    assert len(rows) == ROWS, f"{len(rows)} rows, want {ROWS}"
    seen = set()
    for r in rows:
        line = "".join(t.text or "" for t in r)
        assert len(line) == COLS, f"row width {len(line)}, want {COLS}"
        seen.update(line)
    assert len(seen) >= 4, f"only {len(seen)} distinct chars: image is flat"
    assert " " in seen and RAMP[-1] in seen, "no background or no solid ink"
    print(f"ok {path.name}: {ROWS}x{COLS}, {len(seen)} ramp chars, {path.stat().st_size // 1024}KB")


if __name__ == "__main__":
    rng = random.Random(SEED)
    grid = ramp_grid()
    churn = pick_churn(grid, rng)
    dst = ROOT / "assets" / "ascii.svg"
    dst.write_text(build(grid, churn, random.Random(SEED)), encoding="utf-8")
    self_check(dst)
    if "--self-check" not in sys.argv:
        print("\n".join("".join(RAMP[v] for v in row) for row in grid))
